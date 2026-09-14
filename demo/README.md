# demo

两个 demo，都是**真实产物**，不是摆拍。

## 1. 成果回放（demo.gif）

三帧循环：索引首页 → 索引条目页 → 原书高亮页。

```bash
# 依赖: npm i gifenc pngjs
bash demo/render_frames.sh <索引.docx> <标注版.pdf> <标注页号> demo/frames
node demo/make_gif.mjs demo/frames/index-01.png demo/frames/index-02.png demo/frames/annotated-012.png demo/demo.gif
```

帧由真实交付物渲染而来（Word → PDF → PNG；标注版 PDF 直接渲染），
所以任何人拿自己的产物都能重录，不需要原作者的机器。

## 2. 终端回放（terminal.gif）

```bash
brew install vhs
vhs demo/demo.tape
```

`demo.tape` 里是真实命令：跑流水线、对审计、生成语义候选。

## 为什么 GIF 用 Node 组装而不是 ffmpeg

因为不依赖系统里有没有 ffmpeg/ImageMagick——只要有 Node 和两个纯 JS 包
（gifenc、pngjs）就能重录。减少复现门槛。
