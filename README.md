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
  - `x`, `y` and `z`: Correspond to `source`, `filtered_a` and `filtered_b`, respectively
  - `minimum`: Lowest possible value for the plane. -0.5 for chroma planes in float clips, everything else is 0
  - `neutral`: A null MakeDiff pixel. `128` for 8 bit, `32768` for 16 bit, `0` for float
  - `peak`: Highest possible value for the plane. 255/65535/1/0.5 for 8 bit/16 bit/float luma/float chroma
  - `a`, `b` and `c`: Clips provided via the `ref` parameter. I have no idea if this would ever be useful or if it even works since I didn't test it

### xpassfilter
```
zzfunc.xpassfilter(clip, prefilter, lofilter=None, hifilter=None, safe=True, planes=None)
```
A simple wrapper for `std.MakeDiff` and `std.MergeDiff` that works as so:
```
clip = xpassfilter(clip, prefilter=core.std.BoxBlur, lofilter=core.dfttest.DFTTest, hifilter=core.std.Median, safe=True)

# is the same as...

loclip = core.std.BoxBlur(clip)
hiclip = core.std.MakeDiff(clip, loclip)
loclip = core.std.MakeDiff(clip, hiclip) # safety feature for integer clips

loclip = core.dfttest.DFTTest(loclip)
hiclip = core.std.Median(hiclip)

clip = core.std.MergeDiff(loclip, hiclip)
```

### padding
```
zzfunc.pad(clip, left=0, right=0, top=0, bottom=0, planes=None)
```
Pad the borders of a clip to compensate for filters that behave badly at the edge of clips. Uses `resize.Point` for 8 bit and `fmtc.resample` for other formats. Since zimg works in 8 bit, it will be faster than fmtc, but fmtc's method of copying only the edge pixel (as opposed to mirroring the image) is faster than zimg otherwise.

### shiftplanes
```
zzfunc.shiftplanes(clip, x=[0], y=[0], planes=None, nop=2)
```
Shift the planes of a clip up, down, left or right.

When chroma values are supplied for `x` and `y` they are not relative to chroma subsampling, so for `x=[10,10,10]` a 4:2:0 clip will look mangled. This is not an issue with `x=10` as the per=plane parameter copying will compensate for this when not enough values are given.

### shiftframes
```
zzfunc.shiftframes(clip, origin=0):
```
Shifts the frames of a clip so frame number *origin* is frame 0

### shiftframesmany
```
zzfunc.sfm(clip, radius=[1, 1])
```
Create a clip array of shifted clips. Default setting is identical to `[shiftframes(clip, -1), clip, shiftframes(clip, 1)]`

### mixed_depth
```
zzfunc.mixp(src_hi, flt_hi, src_lo, flt_lo, planes=None)
```
Expr wrapper for preserving high depth information when processing with plugins that don't support high precision formats.

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
Give `clipa` an array and it will behave like vsutil's

Give `clipa` an array and also supply `clipb` or `clipc` and it will substitute them for the corresponding clip from `clipa`

Give it 2 clips (either as an array or as single clips) and it will behave like `mergechroma`

Give one clip each to `clipa`, `clipb` and `clipc` in your vpy scripts because fuck typing `[]` every time
### get_w
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
