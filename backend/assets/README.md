Place `DejaVuSans-Bold.ttf` here for higher-quality annotation labels.

Without it, `perception/annotator.py` falls back to Pillow's built-in bitmap font automatically — the agent still works, labels are just smaller.

Fetch it with:

```bash
curl -L -o DejaVuSans-Bold.ttf \
  https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/DejaVuSans-Bold.ttf
```
