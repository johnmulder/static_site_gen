# Static Assets

This directory contains static assets (CSS, JavaScript, images, etc.) that are copied directly to the generated site without processing.

## Directory Structure

```
static/
├── css/
│   └── style.css      # Main site stylesheet
├── js/                # JavaScript files (if needed)
├── images/            # Site images, logos, etc.
└── favicon.ico        # Site favicon
```

## Asset Processing

Static assets are copied directly to the output directory at `site/static/` during the build process. No processing or minification is performed - files are copied as-is.

## URL References

Static assets can be referenced in templates using:

- CSS: `/static/css/style.css`
- JavaScript: `/static/js/main.js`
- Images: `/static/images/logo.png`

## Basic CSS Structure

The main stylesheet should include:

- Typography and base styles
- Layout for header, content, footer
- Post styling (dates, tags, content)
- Responsive design patterns
- Print styles (optional)

Keep styles simple and maintainable, focusing on readability and clean presentation.
