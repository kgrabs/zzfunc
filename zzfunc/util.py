import vapoursynth as vs
from vsutil import iterate, fallback, depth, get_subsampling, get_plane_size, insert_clip
from functools import partial
from string import ascii_lowercase, ascii_uppercase
from math import floor, ceil, log2

abc = [f' {x} ' for x in ascii_lowercase]
xyz = [f' {x} ' for x in 'xyz'+ascii_lowercase[:-3]]



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
    for x in planes:
        if x >= numplanes:
            planes = planes[:planes.index(x)]
            break
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
