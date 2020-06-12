# zzfunc
A small collection of Vapoursynth scripts of varying usefulness

## Functions from zzfunc.util

### MinFilter
```
zzfunc.minfilter(source, filtered_a, filtered_b, planes=None, strict=True)
```
Pixelwise function that takes the stronger of two filtered clips

Possible values for the bint array `strict`:

 - True: Pass the source pixel when filtered pixels are not homologous to the input (one is darker and the other is brighter)
 - False: Pass the pixel that changed the least
 
### MaxFilter
```
zzfunc.maxfilter(source, filtered_a, filtered_b, planes=None, strict=False, ref=None)
```
Pixelwise function that takes the stronger of two filtered clips

Set `strict` to whatever you want to happen when the filtered pixels aren't homologous to the source pixel.
- False: Just take whichever pixel changed the most **(default)**
- True: Take the average of the filtered clips (just a convenience so you dont have to type `'y z + 2 /'`)
- Supply a RPN string for custom output. Syntax is as follows:
  - `'x'`, `'y'` and `'z'`: Correspond to `source`, `filtered_a` and `filtered_b`, respectively
  - `'minimum'`: Lowest possible value for the plane. -0.5 for chroma planes in float clips, everything else is 0
  - `'neutral'`: A null MakeDiff pixel. `128` for 8 bit, `32768` for 16 bit, `0` for float
  - `'peak'`: Highest possible value for the plane. 255/65535/1/0.5 for 8 bit/16 bit/float luma/float chroma
  - `'a'`, `'b'` and `'c'`: Clips provided via the `ref` parameter. I have no idea if this would ever be useful or if it even works since I didn't test it
 
### get_y, get_u, get_v
```
zzfunc.y(clip)
zzfunc.u(clip)
zzfunc.v(clip)
```
### get_r, get_g, get_b
```
zzfunc.r(clip)
zzfunc.g(clip)
zzfunc.b(clip)
```
Outputs an RGB clip where all 3 planes have the *x* plane. Convert to GRAY and process with filters that dont support RGB input (matrix shouldn't matter since all 3 planes are the same)
### split
```
zzfunc.split(clip)
```
Passes arrays untouched

With RGB input it behaves like get_r/g/b
### join
```
zzfunc.join(clipa, clipb=None, clipc=None, colorfamily=None)
```
Give `clipa` an array and it will behave like vsutil.join

Give `clipa` an array and supply `clipb` or `clipc` and it will substitute them for the corresponding clip from `clipa`

Give it 2 clips (either as an array or as single clips in `clipa` and `clipb`) and it will behave like `mergechroma`

Give one clip each to `clipa`, `clipb` and `clipc` is the same as giving `clipa` an array because fuck typing the `[]` with vsutil's version
###get_w
```
zzfunc.w(height, ar=None, even=None, ref=None)
```
Calculate width based on height. Another stolen vsutil function with pointless extra features (and shorter names)

Supply `ref` to calculate the aspect ratio `ar` based on ref's dimensions, otherwise it defaults to 16:9

If `height` is odd, `even` defaults to `False`
### bicubic_c
```
zzfunc.c(b=0.0, fac=2)
```
Auto-calculate the c value for bicubic based on your "b" value.

Set `fac=1` for SoftCubic
### src_left
```
zzfunc.util.src_left(iw=1920., ow=1280.)
```
For resizing GRAY clips containing chroma with MPEG2 placement
### vstoavs, vstomv, vstoplacebo
```
zzfunc.util.vstoavs(planes, numplanes=3)
zzfunc.util.vstoplacebo(planes)
zzfunc.util.vstomv(planes)
```
Convert the common Vapoursynth "planes" format `planes=[0, 1, 2]` to be used by fmtc.resample, mv.DegrainN, and placebo.Deband respectively
