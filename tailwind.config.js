/**** Tailwind CSS config (local build, scans Django templates) ****/
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./**/templates/**/*.html",
    "./templates/**/*.js",
  ],
  safelist: [
    // Garantir que a navbar apareça mesmo se o scan não detectar as classes
    'hidden',
    'flex',
    'md:flex',
    'md:hidden',
    'items-center',
    'gap-2',
    'border-t',
    'border-slate-800',
    'pt-2',
    'bg-slate-900',
    'text-white',
    'max-w-6xl', 'mx-auto', 'px-4', 'py-2', 'space-y-1',
    'text-xs', 'rounded', 'rounded-md',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};