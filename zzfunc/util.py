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



def src_left(iw=1920., ow=1280.): return 0.25*(1.0-iw/ow)



def bicubic_c(b=0.0, fac=2): return (1.0 - abs(b)) / fac



def split(clip):
    if isinstance(clip, list):
        return clip
    fmt = clip.format
    numplanes = fmt.num_planes
    if numplanes == 1:
        return clip
    return [_get_plane(clip, x) for x in range(numplanes)]

def join(clipa, clipb=None, clipc=None, colorfamily=None):
    core = vs.core
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
    colorfamily = fallback(colorfamily, vs.RGB if clips[0].format.colorfamily==vs.RGB else vs.YUV)
    if clips[2] is None:
        return core.std.ShufflePlanes(clips, planes=[0, 1, 2], colorfamily=colorfamily)
    return core.std.ShufflePlanes(clips, planes=[0] * 3, colorfamily=colorfamily)

def mergechroma(luma, chroma, colorfamily=vs.YUV):
    if luma.format.color_family == vs.RGB:
        raise TypeError('zzfunc.mergechroma: RGB not supported')
    if chroma.format.color_family in (vs.RGB, vs.GRAY):
        raise TypeError('zzfunc.mergechroma: no chroma planes found')
    core = vs.core
    return core.std.ShufflePlanes([luma, chroma], [0, 1, 2], colorfamily)

def mergeluma(chroma, luma, colorfamily=vs.YUV): return mergechroma(luma, chroma, colorfamily)



def _get_plane(clip, plane):
    fmt = clip.format
    if fmt.num_planes == 1:
        return clip
    core = vs.core
    if fmt.color_family == vs.RGB:
        return core.std.ShufflePlanes(clip, [plane] * 3, vs.RGB)
    return core.std.ShufflePlanes(clip, plane, vs.GRAY)

get_y, get_u, get_v, get_r, get_g, get_b = [partial(_get_plane, plane=x) for x in (0,1,2,0,1,2)]



def width(height, ar=None, even=None, ref=None):
    even = fallback(even, height%2 == 0)
    if ar is None:
        if ref is not None:
            try:
                ar = ref.width / ref.height
            except ZeroDivisionError:
                raise TypeError('zz.util.width: ref must have constant width/height')
        else:
            ar = 16/9
    width = height * ar
    if even:
        return round(width / 2) * 2
    return round(width)



def parse_planes(planes, numplanes=3, name='filtername'):
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

def vstoavs(planes, numplanes=3): return [3 if x in planes else 1 for x in range(numplanes)]

def vstoplacebo(planes):
    planes = parse_planes(planes, name='util.vstoplacebo')
    return sum(2 ** i for i in planes)

def vstomv(planes): 
    planes = str(planes).strip('[]') \
                        .replace(',','') \
                        .replace(' ','')
    return { '0' : 0, 
             '1' : 1,
             '2' : 2, 
             '12': 3
           }.get(planes, 4)

def avstovs(planes):
    out = []
    for x in range(len(planes)):
        if planes[x] == 3:
            out += [x]
    return out

def append_params(params, length=3):
    if not isinstance(params, list):
        params=[params]
    while len(params)<length:
        params.append(params[-1])
    return params[:length]

# if param[x] is a number less than or equal to "zero" or is explicitly False or None, delete x from "planes"
# if param[x] is a number greater than "zero" or is explicitly True, pass x if it was originally in "planes"
def eval_planes(params, planes, zero=0):
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



# No idea if this will prove useful or not
def GetMatrix(clip, matrix=None, name='getmatrix'):
    
    if matrix is 2:
        matrix = None
    
    if matrix is not None:
        if isinstance(matrix, int):
            return matrix
        matrix = matrix.lower()
        if matrix == 'chromacl':  # Chromaticity derived non-constant luminance system
            return 12
        if matrix == 'chromancl': # Chromaticity derived constant luminance system
            return 13
        if 'u' in matrix:  # Unspecified
            return GetMatrix(clip, matrix=None)
        if 'y' in matrix:  # YCgCo
            return 8
        #if 'o' in matrix:  # opponent color space
            #return 100
        if 'r' in matrix:  # RGB
            return 0
        if 'i' in matrix:  # iCtCb
            return 14
        if 'f' in matrix:  # fcc
            return 4
        if '24' in matrix: # smpte240m
            return 7
        if '4' in matrix:  # bt470bg 
            return 5
        if '6' in matrix or '1' in matrix: # 601/smpte170m
            return 6
        if '7' in matrix:  # bt709
            return 1
        if 'n' in matrix or matrix in ('2', '2020'): # 2020/bt2020nc/2020ncl
            return 9
        #if '8' in matrix or '5' in matrix: # smpte2085
            #return 11
        if '2' in matrix:  # 2020cl/bt2020c/bt2020c
            return 10
        raise ValueError(f'zzfunc.{name}: "matrix" string provided was outlandishly wrong')
    
    frame = clip.get_frame(0)
    _Matrix = frame.props.get('_Matrix', 0)
    
    if _Matrix is not 0:
        return _Matrix
    
    w, h = frame.width, frame.height
    
    if w <= 1024 and h <= 576:
        return 5
    if w <= 2048 and h <= 1536:
        return 1
    return 9
