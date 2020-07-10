import vapoursynth as vs
import havsfunc as haf
import rgvs
from .util import depth, split, join, fallback, iterate, get_y, partial, mixed_depth, append_params, parse_planes



def overlaymask(clip, ncop=None, nced=None, op=None, ed=None, w=None, h=None, thr=50, thr_ed=None, maximum=3, inflate=2, exmask=None, bits=None, mute_exmask=None, black=None, white=None):
    core = vs.core
    
    thr_ed = fallback(thr_ed, thr)
    bits = fallback(bits, clip.format.bits_per_sample if exmask is None else exmask.format.bits_per_sample)
    fmt_yuv = core.register_format(vs.YUV, vs.INTEGER if bits < 32 else vs.FLOAT, bits, 0, 0)
    fmt_gray = core.register_format(vs.GRAY, vs.INTEGER if bits < 32 else vs.FLOAT, bits, 0, 0)
    mask_out = core.std.BlankClip(clip, w, h, fmt_gray.id, color=0) if exmask is None else core.resize.Point(exmask, format=fmt_gray.id, range=1, range_in=1)
    exmask = False if exmask is None else True
    w, h = mask_out.width, mask_out.height
    
    if mute_exmask is not None:
        mask_out = fvf.rfs(mask_out, mask_out.std.BlankClip(color=0), mute_exmask)
    
    if op is not None:
        op = [int(x) for x in op.strip('[]').split()]
        op_creds = clip[op[0]:op[1]+1]
        mask = core.std.Expr([op_creds, ncop], 'x y - abs').std.Binarize(thr)
        mask = core.resize.Point(mask, format=fmt_yuv.id, range=1, range_in=1)
        mask = core.std.Expr(split(mask), 'x y max')
        mask = haf.mt_expand_multi(mask, mode='ellipse', sw=maximum, sh=maximum)
        mask = iterate(mask, core.std.Inflate, inflate)
        mask = core.resize.Spline36(mask, w, h, format=fmt_gray.id)
        if exmask:
            clips = [mask, mask_out[op[0]:op[1]+1]]
            mask = core.std.Expr(clips, 'x y max')
        mask_out = mask_out[:op[0]] + mask + mask_out[op[1]+1:]
    
    if ed is not None:
        ed = [int(x) for x in ed.strip('[]').split()]
        ed_creds = clip[ed[0]:ed[1]+1]
        mask = core.std.Expr([ed_creds, nced], 'x y - abs').std.Binarize(thr_ed)
        mask = core.resize.Point(mask, format=fmt_yuv.id, range=1, range_in=1)
        mask = core.std.Expr(split(mask), 'x y max')
        mask = haf.mt_expand_multi(mask, mode='ellipse', sw=maximum, sh=maximum)
        mask = iterate(mask, core.std.Inflate, inflate)
        mask = core.resize.Spline36(mask, w, h, format=fmt_gray.id)
        if exmask:
            clips = [mask, mask_out[ed[0]:ed[1]+1]]
            mask = core.std.Expr(clips, 'x y max')
        mask_out = mask_out[:ed[0]] + mask + mask_out[ed[1]+1:]
    
    if black is not None:
        mask_out = fvf.rfs(mask_out, mask_out.std.BlankClip(color=0), black)
    
    if white is not None:
        mask_out = fvf.rfs(mask_out, mask_out.std.BlankClip(color=1 if bits==32 else (1<<bits)-1), white)
    
    return mask_out


# some weird idea I had to adapt the binarize threshold of a descale mask based on yuv color values. 
# the defaults are set up for 8 bit input
# i dont remember how it works anymore
def adaptive_error_mask(source, rescaled, ref, yuv_lo=[190, 20, 20], yuv_hi=[200, 40, 40], yuv_midpoint=[0, 128, 128], thr_lo=[4, 7], thr_hi=[9, 11], bw_thr=None, maximum=0, minimum=0, inflate=0, deflate=0, output_depth=None):
    core = vs.core
    
    if isinstance(ref, vs.VideoNode):
        fmt = ref.format
        flt = fmt.sample_type == vs.FLOAT
        bits = fmt.bits_per_sample
        if (fmt.subsampling_w + fmt.subsampling_h) > 0:
            ref = core.resize.Spline36(ref, format=fmt.replace(subsampling_w=0, subsampling_h=0))
        ref = split(ref)
    else:
        fmt = ref[0].format
        flt = fmt.sample_type == vs.FLOAT
        bits = fmt.bits_per_sample
    
    neutral = 0 if flt else (1 << bits - 1)
    
    if isinstance(yuv_midpoint, list):
        if len(yuv_midpoint) != 3:
            raise TypeError('zzfunc.adaptive_error_mask: yuv_midpoint when specified must include all 3 planar values')
    else:
        raise TypeError('zzfunc.adaptive_error_mask: yuv_midpoint when specified must include all 3 planar values')
    
    if not isinstance(yuv_lo, list):
        raise TypeError('zzfunc.adaptive_error_mask: yuv_lo when specified must include all 3 planar values')
    elif len(yuv_lo) != 3:
        raise TypeError('zzfunc.adaptive_error_mask: yuv_lo when specified must include all 3 planar values')
    
    if not isinstance(yuv_hi, list):
        raise TypeError('zzfunc.adaptive_error_mask: yuv_hi when specified must include all 3 planar values')
    elif len(yuv_hi) != 3:
        raise TypeError('zzfunc.adaptive_error_mask: yuv_hi when specified must include all 3 planar values')
    
    if isinstance(thr_lo, int):
        thr_lo = [thr_lo, thr_lo]
    if isinstance(thr_hi, int):
        thr_lo = [thr_hi, thr_hi]
    
    sfmt = source.format
    
    if output_depth is None:
        output_depth = sfmt.bits_per_sample
    
    output_format = sfmt.replace(bits_per_sample=output_depth, sample_type=vs.FLOAT if output_depth==32 else vs.INTEGER)
    
    peak = 1 if output_depth == 32 else ( 1 << output_depth ) - 1
    
    yuv_range = [yuv_hi[0] - yuv_lo[0]]
    yuv_range+= [yuv_hi[1] - yuv_lo[1]]
    yuv_range+= [yuv_hi[2] - yuv_lo[2]]
    
    thr_range_lo = thr_hi[0] - thr_lo[0]
    thr_range_hi = thr_hi[1] - thr_lo[1]
    
    y_mp = ' '                                 if yuv_midpoint[0] == 0 else ' {} - abs '.format(yuv_midpoint[0])
    u_mp = ' {} '.format('abs' if flt else '') if yuv_midpoint[1] == 0 else ' {} - abs '.format(yuv_midpoint[1])
    v_mp = ' {} '.format('abs' if flt else '') if yuv_midpoint[2] == 0 else ' {} - abs '.format(yuv_midpoint[2])
    
    yexpr = ' x {mp} {lo} - {range} / '.format(mp=y_mp, lo=yuv_lo[0], range=yuv_range[0])
    
    if yuv_lo[1]==yuv_lo[2] and yuv_hi[1]==yuv_hi[2]:
        cexpr = ' y {u_mp} z {v_mp} max {lo} - {range} / '.format(u_mp=u_mp, v_mp=v_mp, lo=yuv_lo[1], range=yuv_range[1])
    else: 
        cexpr = ' y {mp} {lo} - {range} / '.format(mp=u_mp, lo=yuv_lo[1], range=yuv_range[1])
        cexpr+= ' z {mp} {lo} - {range} / '.format(mp=v_mp, lo=yuv_lo[2], range=yuv_range[2])
        cexpr+= ' max '
    
    expr_a = yexpr + cexpr + ' max 0 max 1 min '
    
    colormask = core.std.Expr(ref, expr_a, vs.GRAYS)
    
    if maximum:
        colormask = iterate(colormask, core.std.Maximum, maximum)
    if minimum:
        colormask = iterate(colormask, core.std.Minimum, minimum)
    if inflate:
        colormask = iterate(colormask, core.std.Inflate, inflate)
    if deflate:
        colormask = iterate(colormask, core.std.Deflate, deflate)
    
    diff = ' x y - abs '
    
    low  = ' {thr} z {thr_range} * + '.format(thr=thr_lo[0], thr_range=thr_range_lo)
    high = ' {thr} z {thr_range} * + '.format(thr=thr_lo[1], thr_range=thr_range_hi)
    
    interp = ' {diff} {low} - {peak} {high} {low} - / * '.format(diff=diff, low=low, high=high, peak=peak)
    
    expr_b = ' {diff} {low} <= 0 {diff} {high} >= {peak} {interp} ? ? '.format(diff=diff, low=low, high=high, peak=peak, interp=interp)
    
    return core.std.Expr([source, rescaled, colormask], expr_b, output_format)



def dhh(clip, type=3, thr=None, analog=False, thr2=70, smooth=False, **args):
    bits = clip.format.bits_per_sample
    peak = (1 << bits) - 1
    thr = fallback(thr, 2250 if smooth and type==3 else 140)
    if type == 1:
        thr <<= bits - 8
        return rgvs.RemoveGrainM(clip, mode=20, iter=2).std.MakeDiff(clip).std.Binarize(thr).std.Inflate().std.Inflate()
    core = vs.core
    if type == 2:
        return core.std.Expr([clip.std.Binarize(105 << (bits - 8), v0=peak, v1=0).std.Maximum(), clip.std.Binarize(110 << (bits - 8), v0=0, v1=peak).std.Maximum()], 'x y min').std.Deflate()
    if type == 3:
        lines = FastLineDarkenMOD3_dhh(FastLineDarkenMOD3_dhh(clip, thr).std.Convolution([35, 169, 35, 169, 816, 169, 35, 169, 35]), 250, 1, 250, -2)
        return core.std.Expr([Camembert_dhhMod(clip, **args), lines], f'y {thr2 << (bits - 8)} <= x 0 ?')

def Camembert_dhhMod(clip, div=[155, 64, 30], exp=2.5, radius=1, mode='s', blur='gauss', use_cmod=False):
    if not use_cmod:
        return Camembert_dhh(clip, div, exp, radius, mode, blur)
    
    core = vs.core
    fmt = clip.format
    isflt = fmt.sample_type
    bits = min(16, fmt.bits_per_sample)
    peak = (1 << bits) - 1
    shift = bits - 8
    
    clip = split(clip)
    if isflt:
        clip[0] = depth(clip[0], 16, sample_type=0)
    
    matrix = [341,373,341,373,408,373,341,373,341] if mode.lower() == 's' else [714, 781, 714]
    
    camb = Camembert_dhh(clip[0], div, exp, radius, mode, blur)
    
    mmclips = [core.std.Maximum(clip[0]), core.std.Minimum(clip[0])]
    mima = core.std.Expr(mmclips, f'x y - {1 << shift} <= 0 x y - ?')
    mima = core.std.Inflate(mima)
    mima = iterate(mima, partial(core.std.Convolution, matrix=matrix, mode=mode), 2)
    
    core.std.Lut2(camb, mima, planes=0, function=lambda x, y : x & (peak - y))

def Camembert_dhh(clip, div=[155, 64, 30], exp=2.5, radius=1, mode='s', blur='gauss'):
    core = vs.core
    fmt = clip.format
    isflt = fmt.sample_type
    bits = min(16, fmt.bits_per_sample)
    peak = (1 << bits) - 1
    neutral = 1 << (bits - 1)
    
    if bits > 8:
        div = [x * peak / 255 for x in div]
    
    clip = split(clip)
    
    #I wonder what this was supposed to do...
    #if lumaonly:
        #clip = util.get_y(clip)
    #if median == 0 and not lumaonly:
        #clip = core.smoothuv.SmoothUV(clip,3,200,False)
    #else:
        #clip = rgvs.Median(clip, [0, median])
    
    if isflt:
        clip[0] = depth(clip[0], 16, sample_type=0)
    
    GreyCenteredToMask = f'x y - abs {peak / (peak - neutral)} * '
    
    _Blur = partial(rgvs.Blur, radius=radius, mode=mode, blur=blur)
    
    blurclip = iterate(clip[0], _Blur, 2)
    clip[0] = core.std.Expr([clip[0], blurclip], GreyCenteredToMask + f'{div[0]} / {peak} *')
    clip[0] = _Blur(clip[0])
    clip[0] = core.std.Expr(clip[0], f'x {div[1]} / {exp} pow {peak} *')
    clip[0] = iterate(clip[0], _Blur, 2)
    clip[0] = core.std.Expr(clip[0], f'x {div[2]} / {peak} *')
    clip[0] = _Blur(clip[0])
    
    if isflt:
        clip[0] = core.resize.Point(clip[0], format=fmt.replace(color_family=vs.GRAY, subsampling_w=0, subsampling_h=0).id)
    
    return join(clip)

def FastLineDarkenMOD3_dhh(clip, strength=48., prot=5., luma_cap=191., threshold=4., thinning=0.):
    core = vs.core
    
    fmt = clip.format
    bits = fmt.bits_per_sample
    isflt = fmt.sample_type
    peak = 1 if isflt else (1 << bits) - 1
    scalef = peak / 255
    clamp = ' 0 max 1 min ' if isflt else ''
    
    strength /= 128
    luma_cap *= scalef
    threshold *= scalef
    
    clips = split(clip)
    
    exin = core.std.Maximum(clips[0], threshold=peak/(prot + 1)).std.Minimum()
    diff = core.std.Expr([clips[0], exin], f'y {luma_cap} < y {luma_cap} ? x {threshold} + > x y {luma_cap} < y {luma_cap} ? - 0 ? {127 * scalef} + ')
    
    if thinning != 0:
        linemask = core.std.Minimum(diff)
        linemask = core.std.Expr(linemask, 'x {127 * scalef} - {thinning / 16} * {peak} +'+clamp)
        linemask = rgvs.RemoveGrain(linemask, 20)
    
    thick = core.std.Expr([clips[0], exin], f'y {luma_cap} < y {luma_cap} ? x {threshold} + > x y {luma_cap} < y {luma_cap} ? - 0 ? {strength} * x +')
    
    if thinning != 0:
        expr = f'x y {127 * scalef} - {strength} 1 + * +'
        if isflt:
            expr += f'x 255 * y 255 * 127 - {strength} 1 + * + 255 / '
        thin = core.std.Expr([core.std.Maximum(clips[0]), diff], expr+clamp)
    
    clips[0] = thick if thinning == 0 else core.std.MaskedMerge(thin, thick, linemask)
    
    return join(clips)

def slinesm (clip, thr=None, thr2=170, analog=True, autogain=True, edgesm=None, useMedianBlur=-1, noedges=False, mblur=0.1, thrfade=2.46, div=[155, 64, 30], exp=2.5, radius=1, mode='s', blur='gauss', use_cmod=False):
    core = vs.core
    
    clip = get_y(clip)
    
    fmt = clip.format
    isflt = fmt.sample_type
    bits = min(16, fmt.bits_per_sample)
    peak = (1 << bits) - 1
    
    thr = fallback(thr, 100 if mblur == 0 else 200)
    
    if autogain:
        try:
            clip = core.avsw.Eval('clip.coloryuv(autogain=true)', [clip], ['clip'])
        except vs.Error:
            try:
               fmt = clip.format
               clip = core.resize.Point(clip, format=fmt.replace(bits_per_sample=8, sample_type=0).id, dither_type='error_diffusion')
               clip = core.avsw.Eval('clip.coloryuv(autogain=true)', [clip], ['clip'])
               clip = core.resize.Point(clip, format=fmt.id, dither_type='error_diffusion')
            except vs.Error:
                raise vs.Error('AviSynth is required for this function. AVS+ is recommended but unnecessary for 8 bit input.\nIf you have not already, please download avsproxy from https://github.com/sekrit-twc/avsproxy/releases')
    
    edgesm = None if noedges else fallback(edgesm, Camembert_dhhMod(clip, div, exp, radius, mode, blur, use_cmod))
    
    if thr > 0:
        import muvsfunc as muf
        clip = FastLineDarkenMOD3_dhh(clip, thr)
        if mblur != 0:
            clip = muf.Blur(clip, mblur)
    
    clip = FastLineDarkenMOD3_dhh(clip, 250,1,250,-2)
    
    lo = thr2 / thrfade * (peak / 255)
    hi = thr2 * (peak / 255)
    
    if noedges:
        if analog:
            return core.std.Expr(clip, f'x {lo} < {peak} x {hi} > 0 {peak} x {lo} - {peak / (hi - lo)} * - ? ?')
        return core.std.Binarize(clip, 69 * (peak / 255), v0=peak, v1=0)
    
    expr = f'y {lo} < x y {hi} > 0 x y {hi} - {peak / (lo - hi)} * {peak} / * ? ?'
    if not analog:
        expr = f'y {70 * (peak / 255)} > 0 x ?'
    
    return core.std.Expr([edgesm, clip], expr)


def colormask(clip, colors=[128,128,128], error_margin=[3,3,3]):
    clip = core.std.Expr(clip, ['x {} - abs {} > 0 255 ?'.format(colors[x], error_margin[x]) for x in range(3)])
    return clip

# tophf lines mask
def t_linemask(clip, blur=5, thresh=4, str=16, range_in=None, range=None):
    core = vs.core
    fmt = clip.format
    bits = fmt.bits_per_sample
    isflt = fmt.sample_type
    thresh *= 1 if isflt else (1 << bits) - 1
    clamp = '0 max 1 min' if isflt else ''
    
    clip_grayx = get_y(clip)
    clip_gray8 = depth(clip_grayx, 8, range_in=range_in, range=range, dither_type='none')
    
    clip_yuv420p8 = core.resize.Point(clip_gray8, format=vs.YUV420P8)
    blur_yuv420p8 = core.avsw.Eval(f'clip.binomialblur({blur},u=1,v=1)', clips=[clip_yuv420p8], clip_names=['clip'])
    blur_gray8 = get_y(blur_yuv420p8)
    
    blur_grayx = depth(blur_gray8, bits, sample_type=isflt, range_in=range, range=range_in)
    
    if (bits, isflt) != (8, 0):
        blur_grayx = mixed_depth(clip_grayx, blur_grayx, clip_gray8, blur_gray8)
    
    return core.std.Expr([clip_grayx, blur_grayx], f'x {thresh/255} + y < y x - {str} * 0 ?'+clamp)
    
