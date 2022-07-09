# zzfunc
A small collection of Vapoursynth scripts of varying usefulness

## Functions from zzfunc

### mask.overlaymask
```
zzfunc.overlaymask(clip, ncop=None, nced=None, op=None, ed=None, w=None, h=None, thr=50, thr_ed=None, maximum=3, inflate=2, exmask=None, bits=None, mute_exmask=None, black=None, white=None)
```
Function for credit masking using NCOP/NCED files to detect areas that filters such as `descale` would otherwise thrash

### mask.minmax_mask
```
zzfunc.minmax(clip, minarray, maxarray, radius=None, mode='morph')
```
Masking function that uses zzfunc.std.(Max/)Minimum to create area masks. Remember to keep `pass_coordinates_info=True`

Possible values for `mode`:

 - "range": Simple range mask similar to masktools' "minmax" and Dither tools' gradfun3 mask
 - "morph": Morphology mask useful for gradient detection

### resize_mclip
```
zzfunc.resize_mclip(mclip, w=None, h=None)
```
Box scaler intended for mask clips, which can probably be described as "area average" scaling. Essentially the same as fmtconv's "box" kernel, but behaves slightly differently when scaling up by a factor that isn't a whole number. It instead scales up to the next whole number, and downscales to the intended resolution with box scaling.

### tv.Decensor
```
def Decensor(censored, uncensored, radius=5, min_length=3, smooth=6, thr=None, bordfix=10, \
             intra_mask=False, intra_cutoff=0.5, intra_smooth=0, \
             intra_thr_lo=None, intra_shrink_lo=2, intra_grow_lo=15, \
             intra_thr_hi=None, intra_shrink_hi=5, intra_grow_hi=25, \
             intra_grow_post=50, intra_shrink_post=30, intra_deflate_post=20, \
             censored_filtered=None, uncensored_filtered=None, \
             disable_inter=False, debug=0, output_mappings=False, output_path=None)
```
Function for combining clips using the difference to find full and partial censoring, with automatic and manual techniques and various preview/debug features.

#### Parameters
`radius`: The amount of times to shrink the diff after binarizing (see: thr) Used for full-frame decensoring

`min_length`: ideally removes any string of positive (censored) frames shorter than x, in reality it checks whether the temporal neighborhood has a majority of positive frames (50% or more in x * 2 + 1) so if you have for example a repeating sequence of 2 positive, one negative it wont do anything. Should help with motion artifacts and combing

`smooth`: Fades into and out of censored sections, extending the uncensored source further into the censored sections to compensate for low-contrast bits i.e. at the end of video fades

`thr`: Binarize threshold for the diff, used for full-frame decensoring. Defaults are quite low so as to catch tricky censors (i.e. removal of bodily fluids from fair skinned characters)

`bordfix`: Amount to trim from the border of the diff clip. Used for full-frame decensoring

`intra_mask`: Whether to attempt to decensor within a frame, masking the output rather than picking between censored and uncensored frames

`intra_cutoff`: Scale of `0.0 - 1.0` of what amount of a frame can be masked before just swapping in the uncensored frame completely

`intra_smooth`: Same as `smooth` but for the intra-frame mask

`intra_thr_lo`: Similar to `thr`, this one is set low to catch everything that might be a censor/change and isnt expanded much by default (see next two parameters)

`intra_shrink_lo`: Amount of times to call `std.Minimum` on the `intra_lo` mask before expanding

`intra_grow_lo`: Amount of times to call `std.Maximum` on the `intra_lo` mask after shrinking

`intra_thr_hi`: Similar to `thr`, this one is set high to find light beams and expand them a very large amount (see next two parameters) to account for the effects that beams cause

`intra_shrink_hi`: Amount of times to call `std.Minimum` on the `intra_hi` mask before expanding

`intra_grow_hi`: Amount of times to call `std.Maximum` on the `intra_hi` mask after shrinking

`intra_grow_post`: After `intra_lo` and `intra_hi` are combined into one clip, this parameter controls the amount of `std.Maximum` calls to perform, primarily to close gaps in the mask 

`intra_shrink_post`: Amount of times to shrink the combined intra-frame mask using `std.Minimum` after the previous parameter's expansion operation

`intra_deflate_post`: Also shrinks using `std.Minimum` but with a threshold of `peak/intra_deflate_post` creating an effect similar to cascading many calls to inflate/deflate. You will notice the defaults of this and `intra_shrink_post` are equal to `intra_grow_post` when combined

`censored_filtered`: alternative prefiltered clip that will only be used during final merging for output

`uncensored_filtered`: alternative prefiltered clip that will only be used during final merging for output

`disable_inter`: Disables the full-frame portion of the decensor, mainly to save cpu usage when doing debug-assisted manual decensoring

`debug`: Allows for preview and splicing to assist with parameter tweaking and manual decensoring
 - `0`: Disabled
 - `1`: Simple full-frame debug mode. Previews the output with a text message in the top-left corner showing whether a frame has been decensored or not. Does not use alternative clips so as to speed up seek time
 - `2`: Inter-frame debug mode. Stacks the clip and final inter-frame mask clip together
 - `3`: Splice mode, returns only frames that the full-frame decensorer has deemed censored, stacking both clips and returning them with their frame number in the top left to aid in manual decensoring. May take a long time to process so if you're using Vapoursynth Editor (2) make sure you hit F5 and not F6!

`output_mappings`: Writes a file with censored mappings for replaceframes in lvsfunc format

`output_path`: Full file name and path for the mappings file

### std.MinFilter
```
zzfunc.minfilter(source, filtered_a, filtered_b, planes=None, strict=True)
```
Pixelwise function that takes the stronger of two filtered clips

Possible values for the bint array `strict`:

 - True: Pass the source pixel when filtered pixels are not homologous to the input (one is darker and the other is brighter)
 - False: Pass the pixel that changed the least
 
### std.MaxFilter
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

### std.xpassfilter
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

### std.padding
```
zzfunc.pad(clip, left=0, right=0, top=0, bottom=0, planes=None)
```
Pad the borders of a clip to compensate for filters that behave badly at the edge of clips. Uses `resize.Point` for 8 bit and `fmtc.resample` for other formats. Since zimg works in 8 bit, it will be faster than fmtc, but fmtc's method of copying only the edge pixel (as opposed to mirroring the image) is faster than zimg otherwise.

### std.shiftplanes
```
zzfunc.shiftplanes(clip, x=[0], y=[0], planes=None, nop=2)
```
Shift the planes of a clip up, down, left or right.

When chroma values are supplied for `x` and `y` they are not relative to chroma subsampling, so for `x=[10,10,10]` a 4:2:0 clip will look mangled. This is not an issue with `x=10` as the per=plane parameter copying will compensate for this when not enough values are given.

### std.shiftframes
```
zzfunc.shiftframes(clip, origin=0):
```
Shifts the frames of a clip so frame number *origin* is frame 0

### util.mixed_depth
```
zzfunc.mixp(src_hi, flt_hi, src_lo, flt_lo, planes=None)
```
Expr wrapper for preserving high depth information when processing with plugins that don't support high precision formats.

### util.get_y, util.get_u, util.get_v
```
zzfunc.y(clip)
zzfunc.u(clip)
zzfunc.v(clip)
```
### util.get_r, util.get_g, util.get_b
```
zzfunc.r(clip)
zzfunc.g(clip)
zzfunc.b(clip)
```
Outputs an RGB clip where all 3 planes have the *x* plane. Convert to GRAY and process with filters that dont support RGB input (matrix shouldn't matter since all 3 planes are the same)
### util.split
```
zzfunc.split(clip)
```
Passes arrays untouched

With RGB input it behaves like get_r/g/b
### util.join
```
zzfunc.join(clipa, clipb=None, clipc=None, colorfamily=None)
```
Give `clipa` an array and it will behave like vsutil's

Give `clipa` an array and also supply `clipb` or `clipc` and it will substitute them for the corresponding clip from `clipa`

Give it 2 clips (either as an array or as single clips) and it will behave like `mergechroma`

Give one clip each to `clipa`, `clipb` and `clipc` in your vpy scripts because fuck typing `[]` every time
### util.get_w
```
zzfunc.w(height, ar=None, even=None, ref=None)
```
Calculate width based on height. Another stolen vsutil function with pointless extra features (and shorter names)

Supply `ref` to calculate the aspect ratio `ar` based on ref's dimensions, otherwise it defaults to 16:9

If `height` is odd, `even` defaults to `False`
### util.bicubic_c
```
zzfunc.c(b=0.0, fac=2)
```
Auto-calculate the c value for bicubic based on your "b" value.

Set `fac=1` for SoftCubic
