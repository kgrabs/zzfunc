import vapoursynth as vs
import vsrgtools as rgvs
from .util import split, join, parse_planes, append_params, fallback, get_y, ascii_lowercase, xyz, vs_to_fmtc, log2, partial



def Tweak(clip, hue=None, sat=None, bright=None, cont=None, \
          relative_sat=None, \
          range_in=None, range=None, range_scale=None, \
          bits=None, bits_scale=None, \
          sample=None, sample_scale=None, \
          clamp=True, pre=None, post=None):
    core = vs.core
    from math import sin, cos

    if clip.format is None:
        raise vs.Error("Tweak: only clips with constant format are accepted.")
    
    bits_in = clip.format.bits_per_sample
    sample_in = clip.format.sample_type
    
    def _get_range_prop(clip):
        frame = clip.get_frame(0)
        if '_ColorRange' in frame.props:
            return 1 - frame.props._ColorRange
        return 0
    
    if sample_in == 0:
        range_in         = fallback(range_in, _get_range_prop(clip))
        peak_in          = (1 << bits_in) - 1
        luma_min_in      = 0 if range_in else 16 << (bits_in - 8)
        luma_size_in     = peak_in if range_in else 219 << (bits_in - 8)
        chroma_size_in   = peak_in if range_in else 224 << (bits_in - 8)
        chroma_center_in = 1 << (bits_in - 1)
    else:
        range_in         = 1
        luma_min_in      = 0
        luma_size_in     = 1
        chroma_size_in   = 1
        chroma_center_in = 0
    
    bits_scale = fallback(bits_scale, bits_in)
    sample_scale = fallback(sample_scale, sample_in)
    range_scale = fallback(range_scale, range_in)
    
    bits = fallback(bits, bits_in)
    sample = 0 if bits < 16 else fallback(sample, 1 if bits == 32 else sample_in)
    range_ = fallback(range, range_in)
    del range
    
    convert = bits != bits_in or sample != sample_in or range_ != range_in
    
    if sample == 0:
        luma_min      = 0 if range_ else 16 << (bits - 8)
        chroma_min    = luma_min
        peak          = (1 << bits) - 1
        luma_max      = peak if range_ else 235 << (bits - 8)
        luma_size     = peak if range_ else 219 << (bits - 8)
        chroma_max    = peak if range_ else 240 << (bits - 8)
        chroma_size   = peak if range_ else 224 << (bits - 8)
        chroma_center = 1 << (bits - 1)
    else:
        range_        = 1
        luma_min      = 0
        chroma_min    = -0.5
        luma_max      = 1
        luma_size     = 1
        chroma_max    = 0.5
        chroma_size   = 1
        chroma_center = 0
    
    bright = fallback(bright, 0)
    cont = fallback(cont, 1)
    
    if isinstance(cont, list):
        zero = 0 if sample_scale or range_scale else 16 << (bits_scale - 8)
        if len(cont) < 2: # assume white is the target value
            cont += [1 if sample_scale else (1 << bits_scale) - 1 if range_scale else 235 << (bits_scale - 8)]
        cont = (cont[1] - zero)/(cont[0] - zero)
    
    if relative_sat is not None: # might be broken when cont < 1 and relative_sat > 1
        if cont == 1 or relative_sat == 1:
            sat = cont
        else:
            sat = (cont - 1) * relative_sat + 1

    hue = fallback(hue, 0)
    sat = fallback(sat, 1)
    
    cont = max(cont, 0)
    sat = max(sat, 0)
    
    if (hue == bright == 0) and (sat == cont == 1):
        if convert:
            return depth(clip, bitdepth=bits, sample_type=sample, range=range, range_in=range_in)
        return clip
    
    if callable(pre):
        pre = pre(clip)
    else:
        pre = fallback(pre, clip)
    
    clips = [pre]
    yexpr = ''
    cexpr = ''

    if (hue != 0 or sat != 1 or convert) and clip.format.color_family != vs.GRAY:
        if chroma_size_in != chroma_size:
            sat *= chroma_size / chroma_size_in
        
        hue *= pi / 180.0
        hue_sin = sin(hue)
        hue_cos = cos(hue)
        
        normalize = '' if sample else f' {chroma_center_in} - '
        
        # normalize & apply sat/conversion
        cexpr = f' x {normalize} {hue_cos * sat} * '
        
        if hue != 0: # apply hue if needed
            clips += [pre.std.ShufflePlanes([0,2,1], vs.YUV)]
            cexpr += f' y {normalize} {hue_sin * sat} * + '
        
        if sample == 0:
            cexpr += f' {chroma_center} +'
        
        if clamp and not (sample == 0 and range_):
            cexpr += f' {chroma_min} max {chroma_max} min '

    if bright != 0 or cont != 1 or convert:
        if luma_size_in != luma_size:
            cont *= luma_size / luma_size_in
        
        yexpr = ' x '
        
        if luma_min_in > 0:
            yexpr += f' {luma_min_in} - '
        
        if cont != 1:
            yexpr += f' {cont} * '
        
        if (luma_min + bright) != 0:
            yexpr += f' {luma_min + bright} + '
        
        if clamp and not (sample == 0 and range_):
            yexpr += f' {luma_min} max {luma_max} min '
    
    tweak_clip = core.std.Expr(clips, [yexpr, cexpr])
    
    if callable(post):
       return post(tweak_clip)

    return tweak_clip



def M__imum(clip, video_function, radius=1, coordinates=None, mode='ellipse', pass_coordinates_info=True, **params):
    if coordinates is None:
        if mode == 'ellipse':
            coordinates = [[1]*8, [0,1,0,1,1,0,1,0], [0,1,0,1,1,0,1,0]]
        elif mode == 'losange':
            coordinates = [[0,1,0,1,1,0,1,0]]
        else:
            coordinates = [[1]*8]
    elif isinstance(coordinates[0], int):
        coordinates = [coordinates]
    
    output = [clip]
    
    for i in range(radius):
        output += [video_function(clip=output[-1], coordinates=coordinates[i % len(coordinates)], **params)]
    
    if pass_coordinates_info:
        output[0] = coordinates
    
    return output

Maximum = partial(M__imum, video_function=vs.core.std.Maximum)
Minimum = partial(M__imum, video_function=vs.core.std.Minimum)



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
    
    ps = [strict[x] for x in planes]
    if len(set(ps)) == 1:
        if ps[0]:
            return core.std.Interleave([source, filtered_a, filtered_b]).tmedian.TemporalMedian(1, planes)[1::3]
    
    expr = ['' if x not in planes else 'x y z min max y z max min' if strict[x] else 'x y - abs x z - abs < y z ?' for x in range(numplanes)]
    
    return core.std.Expr(clips, )

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
        return core.fmtc.resample(clip, clip.width+left+right, clip.height+top+bottom, -left, -top, clip.width+left+right, clip.height+top+bottom, kernel='point', planes=vs_to_fmtc(planes, numplanes))
    return core.resize.Point(clip, clip.width+left+right, clip.height+top+bottom, src_left=-left, src_top=-top, src_width=clip.width+left+right, src_height=clip.height+top+bottom)



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



def Deviation(clip, radius, mode='stdev', planes=None):
    core = vs.core
    numplanes = clip.format.num_planes
    planes = parse_planes(planes, numplanes, 'deviation')
    bblur = rgvs.Blur(clip, radius, planes=planes, blur='box')
    expr = 'x y - abs'
    if mode.lower()[0] == 's':
        expr += ' dup *'
    return core.std.Expr([clip, bblur], [expr if x in planes else '' for x in range(numplanes)])
                                 
