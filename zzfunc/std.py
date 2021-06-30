import vapoursynth as vs
import rgvs
from .util import split, join, parse_planes, append_params, fallback, get_y, ascii_lowercase, xyz, vs_to_fmtc, log2



def Resharpen(flt, src, sharpener='gauss 1', prefilter=None, darkened_merge=1, brightened_merge=1, darkening_limit=None, brightening_limit=None, undershoot=0, overshoot=0):
    
    overshoot, undershoot = '', ''
    if overshoot is not None:
        overshoot = f' {overshoot} + '
    if undershoot is not None:
        overshoot = f' {undershoot} - '
    
    flt = split(flt)
    if isinstance(src, vs.VideoNode):
        src = get_y(src)
    else:
        src = [get_y(x) for x in src]
    
    null = 0 if flt[0].format.sample_type else 1 << (flt[0].format.bits_per_sample - 1)
    
    pre = flt[0]
    if prefilter is None:
        pass
    elif isinstance(prefilter, vs.VideoNode):
        pre = prefilter
    elif isinstance(prefilter, int):
        if prefilter < 0:
            pre = rgvs.sbr(pre, r=abs(prefilter))
        else:
            pre = rgvs.MinBlur(pre, r=prefilter)
    else:
        pre = prefilter(pre)
    
    if isinstance(sharpener, str):
        blur = rgvs.Blur(pre, int(sharpener.lower().strip(ascii_lowercase+' ')), bmode=sharpener)
        diff = core.std.MakeDiff(pre, blur)
    else:
        sharp = sharpener(pre)
        diff = core.std.MakeDiff(sharp, pre)
    
    if darkened_merge < 1:
        if darkened_merge <= 0:
            darkening_limit = 0
        else:
            diff = core.std.Expr(diff, 'x {} < x {} * {} x ?'.format(null, darkened_merge, '' if flt[0].format.sample_type else f'{null * (1.0 - darkened_merge)} +'))
    
    if brightened_merge < 1:
        if brightened_merge <= 0:
            brightening_limit = 0
        else:
            diff = core.std.Expr(diff, 'x {} > x {} * {} x ?'.format(null, brightened_merge, '' if flt[0].format.sample_type else f'{null * (1.0 - darkened_merge)} +'))
    
    clamp_expr = ' x '
    
    if darkening_limit is not None:
        clamp_expr += ' {} max '.format(null - darkening_limit)
    
    if brightening_limit is not None:
        clamp_expr += ' {} min '.format(null + brightening_limit)
    
    if darkening_limit is not None or brightening_limit is not None:
        diff = core.std.Expr(diff, clamp_expr)
    
    sharp = core.std.MergeDiff(flt[0], diff)
    
    if isinstance(src, vs.VideoNode):
        clips = [sharp, flt[0], src]
        min_src, max_src = [' z '] * 2
    else:
        clips = [sharp, flt[0]] + src
        xyz = XYZs[:len(src)]
        mi = [' min '] * ( len(src) - 1 )
        ma = [' max '] * ( len(src) - 1 )
        min_src = ''.join(xyz + mi)
        max_src = ''.join(xyz + ma)
        
    return core.std.Expr(clips, 'x y {} min {} max y {} max {} min'.format(min_src, undershoot, max_src, overshoot))



def MinFilter(source, filtered_a, filtered_b, planes=None, strict=True):
    core = vs.core
    
    fmt = source.format
    numplanes = fmt.num_planes
    
    if not fmt==filtered_a.format==filtered_b.format:
        raise TypeError('zzfunc.minfilter: all clips must have the same format')
    
    clips = [source, filtered_a, filtered_b]
    
    planes = parse_planes(planes, numplanes, 'minfilter')
    strict = append_params(strict, numplanes)
    
    # calculating the median is quicker
    # this could be replaced with something like rgvs.Clense or average.Median if there's ever a filter faster than std.Expr
    expr = 'x y - abs x z - abs < y z ?'
    s_expr = 'x y z min max y z max min'
    
    return core.std.Expr(clips, [(s_expr if strict[x] else expr) if x in planes else '' for x in range(numplanes)])

def MaxFilter(source, filtered_a, filtered_b, planes=None, strict=False, ref=None, xor='* 0 <'):
    core = vs.core
    
    fmt = source.format
    numplanes = source.format.num_planes
    bits = fmt.bits_per_sample
    isflt = fmt.sample_type == vs.FLOAT
    
    minimum = [0, -0.5, -0.5] if isflt else [0] * 3
    neutral = 0 if isflt else 1 << (bits - 1)
    peak = [1, 0.5, 0.5] if isflt else [(1 << bits) - 1] * 3
    
    if not fmt==filtered_a.format==filtered_b.format:
        raise TypeError('zzfunc.maxfilter: all clips must have the same format')
    
    clips = [source, filtered_a, filtered_b]
    if ref is not None:
        if isinstance(ref, vs.VideoNode):
            clips += [ref]
        else:
            clips += ref
    
    planes = parse_planes(planes, numplanes, 'maxfilter')
    strict = append_params(strict, numplanes)
    
    # pass the average of the filtered clips when strict=True
    strict = ['y z + 2 /' if strict[x] is True else strict[x] for x in range(numplanes)]
    
    # expression when strict=False
    expr = 'x y - abs x z - abs > y z ?'
    
    # build strict expressions
    s_expr = [f'x y - x z - {xor} {x} {expr} ?' for x in strict]
    
    # replace "minimum", "neutral" and "peak" with i.e. for 8 bit: 0, 128, 255
    #                                                   float luma: 0, 0, 1
    #                                                   float chroma: -0.5, 0, 0.5
    s_expr = [s_expr[x].replace('neutral', f'{neutral}').replace('peak', f'{peak[x]}').replace('minimum', f'{minimum[x]}') for x in range(numplanes)]
    
    return core.std.Expr(clips, [(expr if strict[x] is False else s_expr[x]) if x in planes else '' for x in range(numplanes)])



def xpassfilter(clip, prefilter, lofilter=None, hifilter=None, safe=True, planes=None):
    core = vs.core
    
    fmt = clip.format
    planes = parse_planes(planes, fmt.num_planes, 'xpassfilter')
    
    loclip = prefilter(clip)
    hiclip = core.std.MakeDiff(clip, loclip, planes=planes)
    if fmt.sample_type == vs.INTEGER and safe:
        loclip = core.std.MakeDiff(clip, hiclip, planes=planes)
    
    if lofilter is not None:
        loclip = lofilter(loclip)
    
    if hifilter is not None:
        hiclip = hifilter(hiclip)
    
    return core.std.MergeDiff(loclip, hiclip, planes=planes)



# "planes" parameter not really recommended since it trashes planes, but its there if you need it
def padding(clip, left=0, right=0, top=0, bottom=0, planes=None):
    core = vs.core
    if clip.format.bits_per_sample > 8:
        numplanes = clip.format.num_planes
        planes = parse_planes(planes, numplanes, 'padding')
        return core.fmtc.resample(clip, sx=-left, sy=-top, sw=clip.width+left+right, sh=clip.height+top+bottom, kernel='point', planes=vs_to_fmtc(planes, numplanes))
    return core.resize.Point(clip, src_left=-left, src_top=-top, src_width=clip.width+left+right, src_height=clip.height+top+bottom)



def shiftplanes(clip, x=0, y=0, planes=None, nop=2):
    core = vs.core
    
    fmt = clip.format
    bits = fmt.bits_per_sample
    hss = fmt.subsampling_w
    vss = fmt.subsampling_h
    numplanes = fmt.num_planes
    planes = parse_planes(planes, numplanes, 'shiftplanes')
    fmtcplanes = vs_to_fmtc(planes, numplanes, nop)
    
    x = x if isinstance(x, list) else [x]
    if len(x) == 1:
        x += [x[0] >> hss]
    x = append_params(x, numplanes)
    y = y if isinstance(y, list) else [y]
    if len(y) == 1:
        y += [y[0] >> vss]
    y = append_params(y, numplanes)
    
    if bits > 8:
        for n in range(1, numplanes):
            x[n] <<= hss
            y[n] <<= vss
        return core.fmtc.resample(clip, sx=x, sy=y, kernel='point', planes=fmtcplanes)
    clips = split(clip)
    for p in planes:
        clips[p] = core.resize.Point(clips[p], src_left=x[p], src_top=y[p])
    return join(clips)



def shiftframes(clip, origin=0):
    if origin == 0:
        return clip
    if isinstance(origin, tuple):
        origin = list(origin)
    if isinstance(origin, list):
        step = -1 if origin[0] > origin[1] else 1
        return [shiftframes(clip, x) for x in range(origin[0], origin[1] + step, step)]
    if origin < 0:
        output = clip[0] * abs(origin)
        output += clip[:origin]
    else:
        output = clip[origin:]
        output += clip[-1] * origin
    return output



def Amplify(clip, lo, hi, bits=None, sample=None):
    core = vs.core
    
    fmt = clip.format
    bits_in = fmt.bits_per_sample
    sample_in = fmt.sample_type
    
    bits = fallback(bits, bits_in)
    sample = fallback(sample, sample_in if bits == bits_in else 1 if bits == 32 else 0)
    output_format = core.register_format(vs.GRAY, sample, bits, 0, 0)
    
    peak = 1 if sample else (1 << bits) - 1
    expr = f'x {lo} - {peak/(hi-lo)} *'
    if sample:
        expr += ' 0 max 1 min'
    
    return core.std.Expr(get_y(clip), expr, output_format.id)



def LevelsM(clip, points, levels, xpass=[0, 'peak'], return_expr=False):
    core = vs.core
    qm = len(points)
    peak = [(1 << clip.format.bits_per_sample) - 1, 1][clip.format.sample_type]
    
    if len(set(xpass)) == 1:
        expr = f'x {points[0]} < x {points[-1]} > or {xpass[0]} '
        qm -= 1
    else:
        expr = f'x {points[0]} < {xpass[0]} x {points[-1]} > {xpass[-1]} '
    
    for x in range(len(points) - 1):
        if points[x+1] < points[-1]:
            expr += f' x {points[x+1]} <= '
        if levels[x] == levels[x+1]:
            expr += f' {peak * levels[x]} '
        else:
            expr += f' x {points[x]} - {peak * (levels[x+1] - levels[x])/(points[x+1] - points[x])} * {peak * levels[x]} + '
    
    for _ in range(qm):
        expr += ' ? '
    
    expr = expr.replace(' 0.0 + ', ' ').replace(' 0 + ', ' ').replace(' 0.0 - ', ' ').replace(' 0 - ', ' ').replace('peak', f'{peak}')
    
    if return_expr:
        return expr.replace('  ', ' ')
    
    return core.std.Expr(clip, expr)



def CombineClips(clips, oper='max', planes=None, prefix='', suffix=''):
    core = vs.core
    length = len(clips)
    numplanes = clips[0].format.num_planes
    planes = parse_planes(planes, numplanes, 'CombineClips')
    expr = ''.join(xyz[:length])
    for x in range(length - 1):
        expr += f' {oper} '
    return core.std.Expr(clips, [prefix+expr+suffix if x in planes else '' for x in range(numplanes)])



def Build_a_Blur(clip, weights, radius, strength=log2(3)):
    core = vs.core
    
    clip = core.std.Expr([clip, weights], 'x y *')
    
    matrix = [1]
    weight = 0.5 ** strength / ((1 - 0.5 ** strength) / 2)
    for x in range(radius):
        matrix.append(abs(matrix[-1]) / weight)
    matrix = [matrix[x] for x in range(radius, 0, -1)] + matrix
    
    blur = core.std.Convolution(clip, matrix=matrix, divisor=1, mode='h')
    blur = core.std.Convolution(blur, matrix=matrix, divisor=1, mode='v')
    
    weights = core.std.Convolution(weights, matrix=matrix, divisor=1, mode='h')
    weights = core.std.Convolution(weights, matrix=matrix, divisor=1, mode='v')
    
    return core.std.Expr([blur, weights], 'x y /')



def Deviation(clip, radius, mode='stdev', planes=None):
    core = vs.core
    numplanes = clip.format.num_planes
    planes = parse_planes(planes, numplanes, 'deviation')
    bblur = rgvs.Blur(clip, radius, planes=planes, blur='box')
    expr = 'x y - abs'
    if mode.lower()[0] == 's':
        expr += ' dup *'
    return core.std.Expr([clip, bblur], [expr if x in planes else '' for x in range(numplanes)])
