# Final Submission Artifacts

Generated with:

```bash
python3 scripts/build_submission_artifacts.py --check
```

## Contents

- `proofroute-presentation-updated.pdf`: final designed presentation.
- `proofroute-presentation-updated.pptx`: editable source for the final presentation.
- `proofroute-retro-cli.mp4`: final English presentation video.
- `slides.pdf`: generated reference deck from `submission/slides-outline.md`.
- `cover.png`: generated 16:9 cover image.
- `speaker-notes.md`: short notes generated from the slide outline.
- `demo.mp4`: generated short demo slideshow when `ffmpeg` is available.
- `video-placeholder-approved.md`: historical pre-recording marker; superseded by `proofroute-retro-cli.mp4`.
- `submission-status.json`: strict readiness status for repo, demo, video, CI and public GHCR image.
- `lablab-submit-fields.md`: copy-paste fields for the lablab.ai submission form.

## Final Result

- Image: `ghcr.io/rvbernucci/track1-token-router:v3.12.3-proof-pull-retry`
- Accuracy: 94.7% (18/19)
- Scored Fireworks tokens: 3,051

Post-scoring edits in this directory are documentation corrections only. The submitted source revision, Docker tag and image digests remain unchanged.
