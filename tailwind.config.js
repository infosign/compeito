/** @type {import('tailwindcss').Config} */
// Scans the Jinja templates for utility classes (incl. arbitrary values like
// `grid-cols-[auto_1fr]`) and emits only what is used into src/static/css/app.css.
// Built by the standalone Tailwind binary at Docker image-build time; the output
// is not committed (see .gitignore). Native local dev falls back to the CDN.
module.exports = {
  content: ["./src/templates/**/*.html"],
  theme: {
    extend: {},
  },
  plugins: [],
};
