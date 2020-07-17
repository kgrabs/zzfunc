import vapoursynth as vs
from .util import split, iterate



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
