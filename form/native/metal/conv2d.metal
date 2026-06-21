//
// form-metal conv2d f32 — 2D convolution matching cv2d-conv (form-stdlib/conv2d.fk) EXACTLY,
// the bit-identical Apple-GPU mirror of template_conv2d.ptx. One thread per output element
// (oc, oy, ox). Triple right-fold in the recipe's op order: ky from kh-1 DOWN, kx from kw-1 DOWN
// (cv2d-window-dot / cv-window-dot), ic from IC-1 DOWN (tb-dot), nested accumulators (td per
// pixel, wd per kernel-row, acc total), + bias[oc]. Zero-padding: an out-of-bounds patch pixel
// is a zero vector -> its tb-dot is 0 -> wd += 0 (the ic loop is skipped; 0+wd is bit-identical).
//   out[oy][ox][oc] = bias[oc] + SUM_ky( SUM_kx( tb-dot(W[oc][ky][kx], in[iy][ix]) ) )
//   iy = oy*stride + ky - pad ; ix = ox*stride + kx - pad
// layout: in[(y*Wd+x)*IC+ic], W[((oc*kh+ky)*kw+kx)*IC+ic], out[(oy*outW+ox)*OC+oc].
//
// Bit-exactness: compiled mathMode=.safe (IEEE, no fast-math reassociation/contraction) so the
// `p = W*in; td = p + td;` pair stays two roundings, never an FMA — exactly the PTX mul.f32/add.f32
// pair and the CPU oracle's two-rounding fold. No Metal fast intrinsics (no fma/precise::, no rsqrt).
//
#include <metal_stdlib>
using namespace metal;

// dimensions, mirrored from the PTX .param block — one struct so the host binds it once
struct ConvDims {
    uint ic;      // in-channels
    uint h;       // input height
    uint wd;      // input width
    uint oc;      // out-channels
    uint kh;      // kernel height
    uint kw;      // kernel width
    uint pad;     // zero-pad each side
    uint stride;  // stride in H and W
};

kernel void form_conv2d_f32(
    device const float* W    [[buffer(0)]],   // oc * kh * kw * ic
    device const float* bias [[buffer(1)]],   // oc
    device const float* in   [[buffer(2)]],   // h * wd * ic
    device float*       out  [[buffer(3)]],   // outH * outW * oc
    constant ConvDims&  d    [[buffer(4)]],
    uint                tid  [[thread_position_in_grid]])
{
    // outW = (Wd + 2*pad - kw)/stride + 1 ; outH = (H + 2*pad - kh)/stride + 1  (unsigned div, == PTX)
    uint twoPad = d.pad << 1;
    uint outW = (d.wd + twoPad - d.kw) / d.stride + 1u;
    uint outH = (d.h  + twoPad - d.kh) / d.stride + 1u;

    uint hw    = outH * outW;          // outH*outW
    uint total = d.oc * hw;            // OC*outH*outW
    if (tid >= total) return;

    uint oc  = tid / hw;               // oc = tid/(outH*outW)
    uint rem = tid % hw;
    uint oy  = rem / outW;             // oy = rem/outW
    uint ox  = rem % outW;             // ox = rem%outW

    uint khkwic = d.kh * d.kw * d.ic;  // kh*kw*IC
    uint wbase_oc = oc * khkwic;       // W base for this oc
    uint oys = oy * d.stride;          // oy*stride
    uint oxs = ox * d.stride;          // ox*stride

    float acc = 0.0f;
    uint ky = d.kh;
    while (ky != 0u) {                 // ky from kh DOWN
        ky -= 1u;
        int iy = int(oys) + int(ky) - int(d.pad);   // may be negative
        float wd = 0.0f;
        uint kx = d.kw;
        while (kx != 0u) {             // kx from kw DOWN
            kx -= 1u;
            int ix = int(oxs) + int(kx) - int(d.pad);
            float td = 0.0f;
            // bounds: 0<=iy<H && 0<=ix<Wd — out of bounds -> td stays 0 (zero-pad, bit-identical)
            bool inb = (iy >= 0) && (iy < int(d.h)) && (ix >= 0) && (ix < int(d.wd));
            if (inb) {
                uint wbase = (((ky * d.kw) + kx) * d.ic) + wbase_oc;   // W elem base (oc,ky,kx)
                uint ibase = ((uint(iy) * d.wd) + uint(ix)) * d.ic;    // in elem base (iy,ix)
                uint ic = d.ic;
                while (ic != 0u) {     // ic from IC DOWN  (tb-dot)
                    ic -= 1u;
                    float p = W[wbase + ic] * in[ibase + ic];   // two roundings: mul then add
                    td = p + td;
                }
            }
            wd = td + wd;              // wd = td + wd
        }
        acc = wd + acc;                // acc = wd + acc
    }

    out[((oy * outW + ox) * d.oc) + oc] = acc + bias[oc];   // + bias[oc]
}
