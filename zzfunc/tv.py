import vapoursynth as vs
import havsfunc as haf
import vsrgtools as rgvs
from .util import depth, split, join, fallback, iterate, get_y, partial, mixed_depth, append_params, parse_planes, scale_value
from .std import Maximum, Minimum, shiftframes, CombineClips, Tweak



def Fader(clip, start, end, cont=[None, None], sat=[None, None], bright=[None, None], hue=[None, None], pre=None, post=None, **targs):
    
    if callable(pre):
        pre = pre(clip)
    else:
        pre = fallback(pre, clip)
    
    clipa, clipb = [Tweak(clip, cont=cont[i], sat=sat[i], bright=bright[i], hue=hue[i], pre=pre, post=False, **targs) for i in range(2)]
    
    def _merge(n):
        if n <= start:
            return clipa
        if n >= end:
            return clipb
        return clipa.text.Text(str((n - start) / (end - start)))
        return clipa.std.Merge(clipb, weight=(n - start) / (end - start))
    
    tweak_clip = clip.std.FrameEval(_merge)
    
    if callable(post):
        tweak_clip = post(tweak_clip)
    
    return tweak_clip



def Epilepsy(clip, params, **targs):
    params = [[i] if isinstance(i, int) else list(i) for i in params]

    frames  = []
    cont = []
    sat = []
    bright = []
    hue  = []
    for i in range(len(params)):
        if len(params[i]) == 1: # copy cont+sat from previous entry
            if i is 0:
                params[i] += [None] * 4
            else:
                params[i] += params[i-1][1:]
        while len(params[i]) < 5:
            params[i].append(None)

        frames += [params[i][0]]
        cont   += [params[i][1]]
        sat    += [params[i][2]]
        bright += [params[i][3]]
        hue    += [params[i][4]]
    
    for i in range(len(frames) - 1):
        if frames[i] == frames[i+1]:
            continue
        if (cont[i], sat[i]) == (cont[i+1], sat[i+1]):
            tweak_clip = Tweak(clip, cont=cont[i], sat=sat[i], bright=bright[i], hue=hue[i], **targs)
        else:
            tweak_clip = Fader(clip, start=frames[i], end=frames[i+1], cont=cont[i:i+2], sat=sat[i:i+2], bright=bright[i:i+2], hue=hue[i:i+2], **targs)
            
        clip = clip[:frames[i]] + tweak_clip[frames[i]:frames[i+1]] + clip[frames[i+1]:]
    
    return clip



def Autobalance(clip, target=None, relative_sat=1.0, range_in=0, frame_overrides=[], cont_overrides=[], pre=None, post=None, ref=None, override_mode='interpolate'):
    pre = fallback(pre, clip)
    ref = fallback(ref, clip)
    bits = ref.format.bits_per_sample
    target = fallback(target, scale_value(1, input_depth=32, output_depth=bits, range=range_in, scale_offsets=True, chroma=False))
    
    zero = 16 << (bits - 8) if not range_in and bits < 32 else 0
    target -= zero
    
    ref = ref.std.PlaneStats()
    
    def _scale_ref_val(frame, zero, target): return (target - zero) / (ref.get_frame(frame).props.PlaneStatsMax - zero)
    
    frames = []
    cont_vals = []
    
    for fnums in frame_overrides:
        if isinstance(fnums, int):
            fnums = [fnums, fnums + 1]
            
        prev = _scale_ref_val(fnums[0] - 1, zero, target)
        next = _scale_ref_val(fnums[1], zero, target)
        
        for i in range(fnums[0], fnums[1]):
            frames += [i]
            cont = cont_overrides.pop()
            
            if cont is not None:
                cont_vals += [cont]
            elif mode == 'interpolate':
                weight = (i - (fnums[0] - 1)) / (fnums[1] - (fnums[0] - 1))
                cont_vals += [(prev * (1 - weight)) + (next * weight)]
            elif mode == 'median':
                a = prev
                b = next
                c = _scale_ref_val(i, zero, target)
                cont_vals += [median([a,b,c])]
            else:
                cont_vals += [(prev + next) / 2]
    
    def Autobalance_(n, f):
        if n in frames:
            cont = cont_vals[frames.index(n)]
            sat = ((cont - 1) * relative_sat) + 1
            return Tweak(clip, sat=sat, cont=cont, range_in=range_in)
            
        cont = target / (f.props.PlaneStatsMax - zero)
        sat = (cont - 1) * relative_sat + 1
        
        return Tweak(clip, sat=sat, cont=cont, range_in=range_in)

    return pre.std.FrameEval(Autobalance_, ref)



def Decensor(censored, uncensored, radius=5, min_length=3, smooth=6, thr=None, bordfix=10, \
             intra_mask=False, intra_cutoff=0.5, intra_smooth=0, \
             intra_thr_lo=None, intra_shrink_lo=2, intra_grow_lo=15, \
             intra_thr_hi=None, intra_shrink_hi=5, intra_grow_hi=25, \
             intra_grow_post=50, intra_shrink_post=30, intra_deflate_post=20, \
             censored_filtered=None, uncensored_filtered=None, \
             disable_inter=False, debug=False, output_mappings=False, output_path=None):
    core = vs.core
    
    fmt = censored.format
    scale_bits = 32 if fmt.sample_type == vs.FLOAT else fmt.bits_per_sample
    
    peak = scale_value(255, input_depth=8, output_depth=scale_bits, range_in=1, range=1, scale_offsets=True, chroma=False)
    
    thr = fallback(thr, scale_value(5, input_depth=8, output_depth=scale_bits, range_in=0, scale_offsets=False, chroma=False))
    
    intra_thr_lo = fallback(thr, scale_value(3, input_depth=8, output_depth=scale_bits, range_in=0, scale_offsets=False, chroma=False))
    intra_thr_hi = fallback(thr, scale_value(25, input_depth=8, output_depth=scale_bits, range_in=0, scale_offsets=False, chroma=False))
    
    uncensored_filtered = fallback(uncensored_filtered, uncensored)
    censored_filtered = fallback(censored_filtered, censored)
    
    diff = core.std.Expr([censored, uncensored], 'x y - abs').resize.Point(format=censored.format.replace(subsampling_w=0, subsampling_h=0).id)
    
    if intra_mask:
        intra = core.std.Expr(split(diff), 'x y z max max')
        
        intra_lo_0 = Minimum(intra.std.Binarize(intra_thr_lo), radius=intra_shrink_lo, mode='square')[-1]
        intra_lo = Maximum(intra_lo_0, radius=intra_grow_lo, mode='square')[-1]
        
        intra_hi = intra.std.Binarize(intra_thr_hi)
        intra_hi = Minimum(intra_hi, radius=intra_shrink_hi, mode='square')[-1]
        intra_hi = Maximum(intra_hi, radius=intra_grow_hi, mode='square')[-1]
        
        intra = CombineClips([intra_lo, intra_hi])
        cutoff = CombineClips([intra_lo_0, intra_hi]).fmtc.bitdepth(bits=32,fulls=1).fmtc.resample(1,1,kernel='box').std.Expr(f'x {intra_cutoff} > 1 0 ?',vs.GRAY8).resize.Point(1920, 1080)
        intra = core.std.Expr([intra, cutoff], f'y {peak} x ?')

        intra = Maximum(intra, radius=intra_grow_post)[-1]
        intra = Minimum(intra, radius=intra_shrink_post)[-1]
        threshold = peak / intra_deflate_post
        if scale_bits < 32:
            threshold = round(threshold)
        intra = Minimum(intra, radius=intra_deflate_post, threshold=threshold)[-1]
        if intra_smooth > 0:
            intra_smooth //= 2
            intra = shiftframes(intra, [-intra_smooth, intra_smooth])
            intra = CombineClips(intra)
            intra = core.std.AverageFrames(intra, [1] * ((intra_smooth * 2) + 1))
    
#    ????
#    clip = iterate(diff, core.std.Minimum, radius)
#    censored_clean = censored.rgvs.RemoveGrain(20)
#    uncensored_clean = uncensored.rgvs.RemoveGrain(20)
#    cen_rm = db.rangemask(censored_clean,3,2)
#    unc_rm = db.rangemask(uncensored_clean,3,2)
#    clip = core.std.Expr(
#                         split(core.std.Expr([cen_rm, unc_rm], 'x y - abs') \
#                               .std.Binarize(20 * 256) \
#                               .resize.Point(format=fmt.replace(subsampling_w=0, subsampling_h=0).id)), \
#                         'x y z max max')
#    clip = CombineClips([clip0,clip])
    
    diff = iterate(diff, core.std.Minimum, radius).std.Binarize(thr)
    diff = core.std.Expr(split(diff), 'x y z max max')
    prop_src = diff.std.Crop(bordfix,bordfix,bordfix,bordfix).std.PlaneStats()
    
    def binarize_frame(n, f, clip=diff): return core.std.BlankClip(clip, 1, 1, color=peak if f.props.PlaneStatsMax else 0)

    inter = core.std.FrameEval(core.std.BlankClip(diff, 1, 1), binarize_frame, prop_src=prop_src)
    
    if min_length == 2:
        med = inter.tmedian.TemporalMedian(1)
        inter = core.std.Expr([inter, med], 'x y min')
    if min_length > 2:
        avg = core.std.AverageFrames(inter, [1] * ((min_length * 2) + 1)).std.Binarize(0.5 if scale_bits == 32 else peak // 2)
        inter = core.std.Expr([inter, avg], 'x y min')
    if smooth > 0:
        smooth //= 2
        inter = shiftframes(inter, [-smooth, smooth])
        inter = CombineClips(inter)
        inter = core.std.AverageFrames(inter, [1] * ((smooth * 2) + 1))
    
    if debug == 3:
        clip = inter.std.PlaneStats()
        stacked = core.std.StackVertical([x.text.FrameNum() for x in (censored,uncensored)])
        frames = []
        temp = None
        for i in range(1, clip.num_frames - 1):
            if clip.get_frame(i).props.PlaneStatsMax > 0:
                frames += [stacked[i]]
        return core.std.Splice(frames)

    if output_mappings:
        import os
        clip = inter.std.PlaneStats()
        out_txt = ''
        for i in range(1, clip.num_frames - 1):
            if clip.get_frame(i).props.PlaneStatsMax > 0:
                if clip.get_frame(i - 1).props.PlaneStatsMax > 0:
                    if clip.get_frame(i + 1).props.PlaneStatsMax == 0:
                        out_txt += f'{i + 1}), '
                elif clip.get_frame(i + 1).props.PlaneStatsMax > 0:
                    out_txt += f'({i}, '
                else:
                    out_txt += f'{i}, '
        out_path = fallback(output_path, os.path.expanduser("~") + "/Desktop/censored_sections.txt")
        with open(out_path, "w") as text_file:
            text_file.write(out_txt)
    
    if debug:
        censored_filtered = censored.text.Text('Family Friendly')
        uncensored_filtered = uncensored.text.Text('SEND BOBS')

    def _merge_tits(n, f, cen=censored_filtered, unc=uncensored_filtered):
        weight = f.props.PlaneStatsMax
        if weight == 0:
            return cen
        if intra_mask:
            unc = cen.std.MaskedMerge(unc, intra, [0,1,2], True)
        if weight == peak:
            return unc
        return core.std.Merge(cen, unc, weight/peak)

    clip = core.std.FrameEval(censored_filtered, _merge_tits, prop_src=inter.std.PlaneStats())

    if debug == 2:
        return core.std.StackVertical([clip, intra.resize.Point(format=clip.format.id)])

    if disable_inter:
        if not intra_mask:
            return uncensored_filtered
        return censored_filtered.std.MaskedMerge(uncensored_filtered, intra, [0,1,2], True)

    return clip



def CustomDeblock(clip, db0, db1, db2, db3, edgevalue=24, debug=False, redfix=False,
                adb1=3, adb2=4, adb3=8, adb1d=2, adb2d=7, adb3d=11, range_in=0):
    core = vs.core

    # redfix >8 bit support
    scale_depth = 32 if clip.format.sample_type == vs.FLOAT else clip.format.bits_per_sample
    y_lo = scale_value( 50, input_depth=8, output_depth=scale_depth, range_in=0, range=range_in, scale_offsets=True, chroma=False)
    y_hi = scale_value(130, input_depth=8, output_depth=scale_depth, range_in=0, range=range_in, scale_offsets=True, chroma=False)
    u_lo = scale_value( 95, input_depth=8, output_depth=scale_depth, range_in=0, range=range_in, scale_offsets=True, chroma=True)
    u_hi = scale_value(130, input_depth=8, output_depth=scale_depth, range_in=0, range=range_in, scale_offsets=True, chroma=True)
    v_lo = scale_value(130, input_depth=8, output_depth=scale_depth, range_in=0, range=range_in, scale_offsets=True, chroma=True)
    v_hi = scale_value(155, input_depth=8, output_depth=scale_depth, range_in=0, range=range_in, scale_offsets=True, chroma=True)

    def to8bit(f):
        return f * 0xFF

    def sub_props(clip, f, name):
        OrigDiff_str = str(to8bit(f[0].props.OrigDiff))
        YNextDiff_str = str(to8bit(f[1].props.YNextDiff))
        return core.sub.Subtitle(clip, name + f"\nOrigDiff: {OrigDiff_str}\nYNextDiff: {YNextDiff_str}")

    def eval_deblock_strength(n, f, fastdeblock, debug, unfiltered, fast, weakdeblock,
                              mediumdeblock, strongdeblock):
        unfiltered = sub_props(unfiltered, f, "unfiltered") if debug else unfiltered
        out = unfiltered
        if to8bit(f[0].props.OrigDiff) > adb1 and to8bit(f[1].props.YNextDiff) > adb1d:
            out = sub_props(weakdeblock, f, "weakdeblock") if debug else weakdeblock
        if to8bit(f[0].props.OrigDiff) > adb2 and to8bit(f[1].props.YNextDiff) > adb2d:
            out = sub_props(mediumdeblock, f, "mediumdeblock") if debug else mediumdeblock
        if to8bit(f[0].props.OrigDiff) > adb3 and to8bit(f[1].props.YNextDiff) > adb3d:
            out = sub_props(strongdeblock, f, "strongdeblock") if debug else strongdeblock
        return out

    def fix_red(n, f, unfiltered, autodeblock):
        if (to8bit(f[0].props.YAverage) > y_lo and to8bit(f[0].props.YAverage) < y_hi
                and to8bit(f[1].props.UAverage) > u_lo and to8bit(f[1].props.UAverage) < u_hi
                and to8bit(f[2].props.VAverage) > v_lo and to8bit(f[2].props.YAverage) < v_hi):
            return unfiltered
        return autodeblock

    maxvalue = 1 if clip.format.sample_type == vs.FLOAT else (1 << clip.format.bits_per_sample) - 1
    orig = core.std.Prewitt(clip)
    orig = core.std.Expr(orig, "x {edgevalue} >= {maxvalue} x ?".format(edgevalue=edgevalue, maxvalue=maxvalue))
    orig_d = iterate(orig, partial(rgvs.removegrain, mode=4), 2)

    unfiltered = db0(clip)
    weakdeblock = db1(clip)
    mediumdeblock = db2(clip)
    strongdeblock = db3(clip)

    difforig = core.std.PlaneStats(orig, orig_d, prop='Orig')
    diffnext = core.std.PlaneStats(clip, clip.std.DeleteFrames([0]), prop='YNext')
    autodeblock = core.std.FrameEval(unfiltered, partial(eval_deblock_strength, fastdeblock=fastdeblock,
                                     debug=debug, unfiltered=unfiltered, fast=fast, weakdeblock=weakdeblock,
                                     mediumdeblock=mediumdeblock, strongdeblock=strongdeblock),
                                     prop_src=[difforig,diffnext])

    if redfix:
        clip = core.std.PlaneStats(clip, prop='Y')
        clip_u = core.std.PlaneStats(clip, plane=1, prop='U')
        clip_v = core.std.PlaneStats(clip, plane=2, prop='V')
        autodeblock = core.std.FrameEval(unfiltered, partial(fix_red, unfiltered=unfiltered,
                                         autodeblock=autodeblock), prop_src=[clip,clip_u,clip_v])

    return autodeblock



def iscombed(clip, tff=1, radius=12, output_path=None):
    out_txt = ''
    clip = depth(clip, 8, dither_type='none').vivtc.VFM(tff)
    for i in range(clip.num_frames - 1):
        if clip.get_frame(i).props._Combed:
            if any([clip.get_frame(max(0, min(i - j, clip.num_frames))).props._Combed for j in range(1, radius+1)]):
                if not any([clip.get_frame(max(0, min(i + j, clip.num_frames))).props._Combed for j in range(1, radius+1)]):
                    out_txt += f'{i}]'
            elif any([clip.get_frame(max(0, min(i + j, clip.num_frames))).props._Combed for j in range(1, radius+1)]):
                out_txt += f'[{i} '
            else:
                out_txt += f' {i} '
    import os
    out_path = fallback(output_path, os.path.expanduser("~") + "/Desktop/combed_sections.txt")
    with open(out_path, "w") as text_file:
        text_file.write(out_txt)



def mpeg2stinx(clip, **msargs):
    core=vs.core
    try:
        flt = core.mpeg2stinx.Mpeg2Stinx(clip, **msargs)
    except:
        flt = core.avsw.Eval('clip.mpeg2stinx2()', [depth(clip, 8)], ['clip']).resize.Point(format=clip.format.id)
    analyze = CombineClips(split(core.std.Expr([clip, flt], 'x y - abs').std.Binarize([15,15]).resize.Point(format=vs.YUV444P8))).std.Crop(4,4,4,4).std.AddBorders(4,4,4,4)
    def pick(n, f): return flt if f.props.PlaneStatsAverage > (10 / (1440*1080)) else clip
    return core.std.FrameEval(clip, pick, analyze.std.PlaneStats())
