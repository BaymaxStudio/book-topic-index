// 用真实产物帧组装 demo GIF（纯 JS，无 ffmpeg/ImageMagick 依赖）
// 依赖: npm i gifenc pngjs
import fs from 'node:fs';
import pngjs from 'pngjs';
import gifenc from 'gifenc';

const { PNG } = pngjs;
const { GIFEncoder, quantize, applyPalette } = gifenc;

const args = process.argv.slice(2);
const out = args.pop();
const frames = args;
const W = 620;
const DELAY = Number(process.env.DELAY_MS || 1600);

function load(path) { return PNG.sync.read(fs.readFileSync(path)); }

function scale(src, tw) {
  const th = Math.round(src.height * tw / src.width);
  const dst = new PNG({ width: tw, height: th });
  for (let y = 0; y < th; y++) {
    for (let x = 0; x < tw; x++) {
      const sx = Math.min(src.width - 1, Math.round(x * src.width / tw));
      const sy = Math.min(src.height - 1, Math.round(y * src.height / th));
      const si = (sy * src.width + sx) << 2, di = (y * tw + x) << 2;
      dst.data[di] = src.data[si]; dst.data[di+1] = src.data[si+1];
      dst.data[di+2] = src.data[si+2]; dst.data[di+3] = 255;
    }
  }
  return dst;
}

const imgs = frames.map(f => scale(load(f), W));
const H = Math.max(...imgs.map(i => i.height));
const gif = GIFEncoder();

for (const img of imgs) {
  const canvas = new Uint8Array(W * H * 4).fill(255);
  const oy = Math.floor((H - img.height) / 2);
  for (let y = 0; y < img.height; y++) {
    for (let x = 0; x < W; x++) {
      const si = (y * W + x) << 2, di = ((y + oy) * W + x) << 2;
      canvas[di] = img.data[si]; canvas[di+1] = img.data[si+1];
      canvas[di+2] = img.data[si+2]; canvas[di+3] = 255;
    }
  }
  const palette = quantize(canvas, 256);
  const index = applyPalette(canvas, palette);
  gif.writeFrame(index, W, H, { palette, delay: DELAY });
}
gif.finish();
fs.writeFileSync(out, gif.bytes());
console.log('GIF:', out, fs.statSync(out).size, 'bytes,', imgs.length, 'frames,', W + 'x' + H);
