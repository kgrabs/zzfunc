import vapoursynth as vs
from vsutil import iterate, fallback, depth, get_subsampling, get_plane_size, insert_clip
from functools import partial



def MinFilter(source, filtered_a, filtered_b, planes=None, strict=True):
    core = vs.core
    
    fmt = source.format
    numplanes = fmt.num_planes
    
    if not fmt==filtered_a.format==filtered_b.format:
        raise TypeError('zzfunc.MaxFilter: all clips must have the same format')
    
    clips = [source, filtered_a, filtered_b]
    
    planes = parse_planes(planes, numplanes, 'minfilter')
    strict = append_params(strict, numplanes)
    
    # calculating the median is quicker
    # this could be replaced with something like rgvs.Clense or average.Median if there's ever a filter faster than std.Expr
    expr = 'x y - abs x z - abs < y z ?'
    s_expr = 'x y z min max y z max min'
    
    return core.std.Expr(clips, [(s_expr if strict[x] else expr) if x in planes else '' for x in range(numplanes)])

def MaxFilter(source, filtered_a, filtered_b, planes=None, strict=False, ref=None):
    core = vs.core
    
    fmt = source.format
    numplanes = clip.format.num_planes
    bits = fmt.bits_per_sample
    isflt = fmt.sample_type == vs.FLOAT
    
    minimum = [0, -0.5, -0.5] if isflt else [0] * 3
    neutral = 0 if isflt else 1 << (bits - 1)
    peak = [1, 0.5, 0.5] if isflt else [(1 << bits) - 1] * 3
    
    if not fmt==filtered_a.format==filtered_b.format:
        raise TypeError('zzfunc.MaxFilter: all clips must have the same format')
    
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
    s_expr = [f'x y - x z - xor {x} {expr} ?' for x in strict]
    
    # replace "minimum", "neutral" and "peak" with i.e. for 8 bit: 0, 128, 255
    #                                                   float luma: 0, 0, 1
    #                                                   float chroma: -0.5, 0, 0.5
    s_expr = [s_expr[x].replace('neutral', f'{neutral}').replace('peak', f'{peak[x]}').replace('minimum', f'{minimum[x]}') for x in range(numplanes)]
    
    return core.std.Expr(clips, [(expr if strict[x] is False else s_expr[x]) if x in planes else '' for x in range(numplanes)])



def xpassfilter(clip, prefilter, hifilter=None, lofilter=None, safe=True, planes=None):
    core = vs.core
    
    fmt = clip.format
    planes = parse_planes(planes, fmt.num_planes, 'util.xpassfilter')
    
    loclip = prefilter(clip)
    hiclip = core.std.MakeDiff(clip, loclip, planes=planes)
    if fmt.sample_type == vs.INTEGER and safe:
        loclip = core.std.MakeDiff(clip, hiclip, planes=planes)
    
    if lofilter is not None:
        loclip = lofilter(hiclip)
    
    if hifilter is not None:
        hiclip = hifilter(hiclip)
    
    return core.std.MergeDiff(loclip, hiclip, planes=planes)



# "planes" parameter not really recommended since it trashes planes, but its there if you need it
def padding(clip, left=0, right=0, top=0, bottom=0, planes=None):
    core = vs.core
    if clip.format.bits_per_sample > 8:
        numplanes = clip.format.num_planes
        planes = parse_planes(planes, numplanes, 'util.padding')
        return core.fmtc.resample(clip, sx=-left, sy=-top, sw=clip.width+left+right, sh=clip.height+top+bottom, kernel='point', planes=vs_to_fmtc(planes, numplanes))
    return core.resize.Point(clip, src_left=-left, src_top=-top, src_width=clip.width+left+right, src_height=clip.height+top+bottom)



def shiftplanes(clip, x=0, y=0, planes=None, nop=2):
    core = vs.core
    
    fmt = clip.format
    bits = fmt.bits_per_sample
    hss = fmt.subsampling_w
    vss = fmt.subsampling_h
    numplanes = fmt.num_planes
    planes = parse_planes(planes, numplanes, 'util.shiftplanes')
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



def shiftframesmany(clip, radius=[1, 1]):
    clips = []
    for x in range(-radius[0],0):
        clips += [clip[0] * -x + clip[:x] ]
    clips += [clip]
    for x in range(1, radius[1]+1):
        clips += [clip[x:] + clip[-1] * x]
    return clips

def shiftframes(clip, origin=0):
    if origin == 0:
        return clip
    core = vs.core
    if origin < 0:
        clips = [clip[0] * abs(origin)]
        clips+= [clip[:origin]]
        return core.std.Splice(clips)
    clips = [clip[origin:]]
    clips+= [clip[-1] * origin]
    return core.std.Splice(clips)



def mixed_depth(src_hi, flt_hi, src_lo, flt_lo, planes=None):
    if src_lo.format != flt_lo.format:
        raise vs.Error('zzfunc.util.mixed_depth: Format mismatch with high-depth clips')
    if src_hi.format != flt_hi.format:
        raise vs.Error('zzfunc.util.mixed_depth: Format mismatch with low-depth clips')
    core = vs.core
    numplanes = src_hi.format.num_planes
    planes = parse_planes(planes, numplanes, 'util.mixed_depth')
    return core.std.Expr([src_hi, flt_hi, src_lo, flt_lo], ['z a = x y ?' if x in planes else '' for x in range(numplanes)])



def src_left(iw=1920., ow=1280.): return 0.25*(1.0-iw/ow)

def get_c(b=0.0, fac=2): return (1.0 - abs(b)) / fac

def get_w(height, ar=None, even=None, ref=None):
    even = fallback(even, height%2 == 0)
    if ar is None:
        if ref is not None:
            try:
                ar = ref.width / ref.height
            except ZeroDivisionError:
                raise TypeError('zz.w ref must have constant width/height')
        else:
            ar = 16/9
    width = height * ar
    if even:
        return round(width / 2) * 2
    return round(width)



def split(clip):
    if isinstance(clip, list):
        return clip
    fmt = clip.format
    numplanes = fmt.num_planes
    if numplanes == 1:
        return [clip]
    return [_get_plane(clip, x) for x in range(numplanes)]

def join(clipa, clipb=None, clipc=None, colorfamily=None):
    if isinstance(clipa, list):
        clips = clipa
    elif isinstance(clipa, tuple):
        clips = list(clipa)
    else:
        clips = [clipa]
    while len(clips) < 3:
        clips.append(None)
    if clipb is not None:
        clips[1] = [clipb]
    if clipc is not None:
        clips[2] = [clipc]
    if clips[1] is None:
        return clips[0]
    core = vs.core
    colorfamily = fallback(colorfamily, vs.RGB if clips[0].format.color_family==vs.RGB else vs.YUV)
    if clips[2] is None:
        return core.std.ShufflePlanes(clips, planes=[0, 1, 2], colorfamily=colorfamily)
    return core.std.ShufflePlanes(clips, planes=[0] * 3, colorfamily=colorfamily)



def _get_plane(clip, plane):
    fmt = clip.format
    if fmt.num_planes == 1:
        return clip
    core = vs.core
    if fmt.color_family == vs.RGB:
        return core.std.ShufflePlanes(clip, [plane] * 3, vs.RGB)
    return core.std.ShufflePlanes(clip, plane, vs.GRAY)

get_y, get_u, get_v, get_r, get_g, get_b = [partial(_get_plane, plane=x) for x in (0,1,2,0,1,2)]



def append_params(params, length=3):
    if not isinstance(params, list):
        params=[params]
    while len(params)<length:
        params.append(params[-1])
    return params[:length]

def parse_planes(planes, numplanes=3, name='util.parse_planes'):
    planes = fallback(planes, list(range(numplanes)))
    if isinstance(planes, int):
        planes = [planes]
    if isinstance(planes, tuple):
        planes = list(planes)
    if not isinstance(planes, list):
        raise TypeError(f'zzfunc.{name}: improper "planes" format')
    planes = planes[:min(len(planes), numplanes)]
    if any(x >= numplanes for x in planes):
        raise ValueError(f'zzfunc.{name}: one or more "planes" values out of bounds')
    return planes

# if param[x] is a number less than or equal to "zero" or is explicitly False or None, delete x from "planes"
# if param[x] is a number greater than "zero" or is explicitly True, pass x if it was originally in "planes"
def eval_planes(planes, params, zero=0):
    if not isinstance(params, list):
        raise TypeError('zzfunc.util.eval_planes: params must be an array')
    if not isinstance(planes, list):
        raise TypeError('zzfunc.util.eval_planes: planes must be an array')
    process = []
    for x in range(len(params)):
        if x in planes:
            if params[x] is False or params[x] is None:
                pass
            elif params[x] is True:
                process += [x]
            elif params[x] > zero:
                process += [x]
    return process

def vs_to_fmtc(planes, numplanes=3, nop=1):
    planes = parse_planes(planes, numplanes, name='util.vs_to_fmtc')
    return [3 if x in planes else nop for x in range(numplanes)]

def vs_to_placebo(planes, numplanes=3):
    planes = parse_planes(planes, numplanes, 'util.vs_to_placebo')
    return sum(2 ** i for i in planes) or 1

def vs_to_mv(planes): 
    planes = str(planes).strip('[]') \
                        .replace(',','') \
                        .replace(' ','')
    return { '0' : 0, 
             '1' : 1,
             '2' : 2, 
             '12': 3
           }.get(planes, 4)

def fmtc_to_vs(planes):
    out = []
    for x in range(len(planes)):
        if planes[x] == 3:
            out += [x]
    return out

def f3k_to_vs(y, cb, cr, grainy, grainc):
    planes = []
    params = [sum(x) for x in zip((y, cb, cr), (grainy, grainc, grainc))]
    for x in range(3):
        if params[x] > 0:
            planes += [x]
    return planes
