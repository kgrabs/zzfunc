from vapoursynth import core
from . import util

def Super(clip, hpad=16, vpad=None, pel=2, levels=0, chroma=True, sharp=2, rfilter=2, pelclip=None, opt=True):
    vpad = util.fallback(vpad, hpad)
    if clip.format.sample_type:
        sup = core.mvsf.Super(clip, hpad, vpad, pel, levels, chroma, sharp, rfilter, pelclip)
    else:
        sup = core.mv.Super(clip, hpad, vpad, pel, levels, chroma, sharp, rfilter, pelclip, opt)
    return [sup, hpad, vpad]



def Analyse(super, radius=1, blksize=None, blksizev=None, levels=0, search=4, searchparam=2, pelsearch=0, _lambda=None, chroma=True, truemotion=True, lsad=None, plevel=None, _global=None, pnew=None, pzero=None, pglobal=0, overlap=None, overlapv=None, divide=0, badsad=10000., badrange=None, meander=True, trymany=False, fields=False, tff=None, search_coarse=3, dct=0, opt=True):
    
    radius = util.append_params(radius, 2)
    
    blksizev = util.fallback(blksizev, blksize)
    blksize = util.fallback(blksize, super[1])
    blksizev = util.fallback(blksizev, super[2])
    
    super = super[0]
    ssw, ssh = super.format.subsampling_w, super.format.subsampling_h
    
    overlapv = util.fallback(overlapv, overlap)
    overlapv = util.fallback(overlapv, blksizev >> 1)
    overlap = util.fallback(overlap, blksize >> 1)
    
    overlap = min(overlap, blksize >> 1) >> ssw << ssw)
    overlapv = min(overlapv, blksizev >> 1) >> ssw << ssw)
    
    if super.format.sample_type == vs.FLOAT:
        MAnalyse = core.mvsf.Analyze
    elif blksize == 2:
        raise ValueError('No')
    else:
        MAnalyse = partial(core.mv.Analyse, opt=opt)
        badsad = round(badsad)
    
    if badrange is None:
        badrange = -24 if search in [3,6,7] else 24
    
    def getvecs(isb, delta): return MAnalyse(super, isb=isb, blksize=blksize, blksizev=blksizev, levels=levels, search=search, searchparam=searchparam, pelsearch=pelsearch, _lambda=_lambda, chroma=chroma, delta=delta, truemotion=truemotion, lsad=lsad, plevel=plevel, _global=_global, pnew=pnew, pzero=pzero, pglobal=pglobal, overlap=overlap, overlapv=overlapv, divide=divide, badsad=badsad, badrange=badrange, meander=meander, trymany=trymany, fields=fields, tff=tff, search_coarse=search_coarse, dct=dct)
    
    bv = [getvecs(1, i) for i in range(1, radius+1)]
    fv = [getvecs(0, i) for i in range(1, radius+1)]
    
    blksize >>= 1
    blksizev >>= 1
    if (blksize, blksizev) == (8, 1):
        blksize, blksizev = 2, 2
        overlapv >>= 3
    elif (blksize, blksizev) == (4, 2):
        blksize, blksizev = 4, 4
        overlap >>= 1
    else:
        overlap >>= 1
        overlapv >>= 1
    
    args = dict(blksize=blksize, blksizev=blksizev, search=search, searchparam=searchparam, _lambda=_lambda, chroma=chroma, truemotion=truemotion, _pnew=pnew, overlap=overlap, overlapv=overlapv, divide=divide, meander=meander, fields=fields, tff=tff, dct=dct, thsad=200.)
    
    return [bv, fv, args]

Analyze = Analyse



def Recalculate(super, vectors, radius=None, thsad=None, smooth=None, blksize=None, blksizev=None, search=None, searchparam=None, _lambda=None, chroma=None, truemotion=None, pnew=None, overlap=None, overlapv=None, divide=None, meander=None, fields=None, tff=None, dct=None, opt=True):
    
    radius = util.fallback(radius, [len(x) for x in vectors[:2]]))
    radius = util.append_params(radius, 2)
    thsad = util.fallback(thsad, vectors[2].get(thsad, 200))
    smooth = util.fallback(smooth, vectors[2].get(smooth, 1))
    blksizev = util.fallback(blksizev, blksize)
    blksize = util.fallback(blksize, vectors[2]['blksize'])
    blksizev = util.fallback(blksizev, vectors[2]['blksizev'])
    search = util.fallback(search, vectors[2]['search'])
    searchparam = util.fallback(searchparam, vectors[2]['searchparam'])
    _lambda = util.fallback(_lambda, vectors[2]['_lambda'])
    chroma = util.fallback(chroma, vectors[2]['chroma'])
    truemotion = util.fallback(truemotion, vectors[2]['truemotion'])
    pnew = util.fallback(pnew, vectors[2]['pnew'])
    overlapv = util.fallback(overlapv, overlap)
    overlap = util.fallback(overlap, vectors[2]['overlap'])
    overlapv = util.fallback(overlapv, vectors[2]['overlapv'])
    divide = util.fallback(divide, vectors[2]['divide'])
    meander = util.fallback(meander, vectors[2]['meander'])
    fields = util.fallback(fields, vectors[2]['fields'])
    tff = util.fallback(tff, vectors[2]['tff'])
    dct = util.fallback(dct, vectors[2]['dct'])
    
    overlap = min(overlap, blksize >> 1) >> ssw << ssw)
    overlapv = min(overlapv, blksizev >> 1) >> ssw << ssw)
    
    if super.format.sample_type==vs.FLOAT:
        MRecalculate = core.mvsf.Recalculate
    elif blksize == 2:
        return vectors
    else:
        MRecalculate = partial(core.mv.Recalculate, opt=opt)
        thsad = round(thsad)
    
    def refine(vec): return MRecalculate(super, vec, thsad=thsad, smooth=smooth, blksize=blksize, blksizev=blksizev, search=search, searchparam=searchparam, _lambda=_lambda, chroma=chroma, truemotion=truemotion, pnew=pnew, overlap=overlap, overlapv=overlapv, divide=divide, meander=meander, fields=fields, tff=tff, dct=dct)
    
    bv = [refine(x) for x in vectors[0][:radius[0]]
    fv = [refine(x) for x in vectors[1][:radius[1]]
    
    blksize >>= 1
    blksizev >>= 1
    if (blksize, blksizev) == (8, 1):
        blksize, blksizev = 2, 2
        overlapv >>= 3
    elif (blksize, blksizev) == (4, 2):
        blksize, blksizev = 4, 4
        overlap >>= 1
    else:
        overlap >>= 1
        overlapv >>= 1
    
    args = dict(thsad=thsad/2, smooth=smooth, blksize=blksize, blksizev=blksizev, search=search, searchparam=searchparam, _lambda=_lambda, chroma=chroma, truemotion=truemotion, _pnew=pnew, overlap=overlap, overlapv=overlapv, divide=divide, meander=meander, fields=fields, tff=tff, dct=dct, thsad=200.)
    
    return [bv, fv, args]



def Compensate(clip, super, vectors, radius=None, cclip=None, scbehavior=1, thsad=10000.0, thsad2=None, fields=False, time=100.0, thscd1=400.0, thscd2=130.0, tff=None, interleaved=True, opt=True):
    
    radius = util.fallback(radius, min(len(x) for x in vectors[:2]))
    tff = util.fallback(tff, vectors[2]['tff'])
    
    vectors = Interleave(vectors, radius)
    
    if super.format.sample_type==vs.FLOAT:
        if thsad2 is not None or len(set(radius)) == 1:
            comp = core.mvsf.Compensate(clip, super[0], vectors, cclip, scbehavior, thsad, thsad2, fields, time, thscd1, thscd2, tff)
            if interleaved:
                return comp
            return Disperse(comp, radius)
        MCompensate = core.mvsf.Compensate
    else:
        MCompensate = partial(core.mv.Compensate, opt=opt)
        thsad    = round(thsad[0])
        thscd1   = round(thscd1)
        thscd2   = round(thscd2)
        
    cclip = util.fallback(cclip, clip)
    
    def comp(isb, delta): return MCompensate(clip, super[0], vectors[1 - isb][abs(delta)], scbehavior=scbehavior, thsad=thsad, fields=fields, time=time, thscd1=thscd1, thscd2=thscd2, tff=tff)
    
    bcomp = [comp(1, i) for i in range(radius]
    fcomp = [comp(0, i) for i in range(radius)]
    comp = bcomp + [cclip] + fcomp
    
    if interleaved:
        return core.std.Interleave(comp)
    return comp



def Degrain(clip, super, vectors, radius=None, thsad=400., thsad2=None, planes=None, limit=None, thscd1=400., thscd2=130., opt=True):
    
    numplanes = clip.format.num_planes
    radius = util.fallback(radius, min(len(x) for x in vectors[:2])
    thsad = util.append_params(thsad, numplanes)
    if thsad2 is not None:
        thsad2 = util.append_params(thsad2, numplanes)
    planes = util.parse_planes(planes, numplanes, 'mv.Degrain')
    planes = util.vs_to_mv(planes)
    limit = util.append_params(limit, numplanes)
    
    if clip.format.sample_type == vs.INTEGER:
        thsadc = round(thsad[-1])
        thsad = round(thsad[0])
        limitc = round(limit[-1])
        limit = round(limit[0])
        thscd1 = round(thscd1)
        thscd2 = round(thscd2)
        args = dict(clip=clip, super=super[0], mvbw=vectors[0][0], mvfw=vectors[1][0], thsad=thsad, thsadc=thsadc, plane=planes, limit=limit, limitc=limitc, thscd1=thscd1, thscd2=thscd2, opt=opt)
        if radius == 1:
            return core.mv.Degrain1(**args)
        if radius == 2:
            return core.mv.Degrain2(mvbw2=vectors[0][1], mvfw2=vectors[1][1], **args)
        return core.mv.Degrain3(mvbw2=vectors[0][1], mvfw2=vectors[1][1], mvbw3=vectors[0][2], mvfw3=vectors[1][2], **args)
    
    mvmulti = Interleave(vectors, radius)
    
    return core.mvsf.Degrain(clip, super[0], mvmulti, thsad, thsad2, plane, limit, thscd1, thscd2)



def Interleave(vectors, radius):
    bv = vectors[0][:radius]
    fv = vectors[1][:radius]
    bv.reverse()
    return core.std.Interleave(bv+fv)



def Disperse(vectors, radius):
    bv = vectors[0][:radius]
    fv = vectors[1][:radius]
    vectors = bv+fv
    return [vectors[x::radius * 2 + 1] for x in range(radius * 2 + 1)]
    
