import { color } from '@oclif/color';

// Large ASCII art for "Klarvido"
const ASCII_KLARVIDO = [
  '██╗  ██╗██╗      █████╗ ██████╗ ██╗   ██╗██╗██████╗  ██████╗ ',
  '██║ ██╔╝██║     ██╔══██╗██╔══██╗██║   ██║██║██╔══██╗██╔═══██╗',
  '█████╔╝ ██║     ███████║██████╔╝██║   ██║██║██║  ██║██║   ██║',
  '██╔═██╗ ██║     ██╔══██║██╔══██╗╚██╗ ██╔╝██║██║  ██║██║   ██║',
  '██║  ██╗███████╗██║  ██║██║  ██║ ╚████╔╝ ██║██████╔╝╚██████╔╝',
  '╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚═════╝  ╚═════╝ ',
];

// Gradient colors: yellow (255, 254, 37) -> green (66, 242, 114)
const GRADIENT_START = { r: 255, g: 254, b: 37 };
const GRADIENT_END = { r: 66, g: 242, b: 114 };

interface RGB {
  r: number;
  g: number;
  b: number;
}

/**
 * Interpolate between two colors
 */
function interpolateColor(start: RGB, end: RGB, factor: number): RGB {
  return {
    r: Math.round(start.r + (end.r - start.r) * factor),
    g: Math.round(start.g + (end.g - start.g) * factor),
    b: Math.round(start.b + (end.b - start.b) * factor),
  };
}

/**
 * Apply color to text using ANSI true color
 */
function colorText(text: string, rgb: RGB): string {
  return `\x1b[38;2;${rgb.r};${rgb.g};${rgb.b}m${text}\x1b[0m`;
}

/**
 * Apply gradient to a line of text
 */
function applyGradientToLine(line: string): string {
  if (line === '') return '';

  let result = '';
  let charIndex = 0;
  const totalChars = line.replace(/\s/g, '').length;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === ' ') {
      result += char;
    } else {
      const progress = charIndex / Math.max(totalChars - 1, 1);
      const rgb = interpolateColor(GRADIENT_START, GRADIENT_END, progress);
      result += colorText(char, rgb);
      charIndex++;
    }
  }
  return result;
}

/**
 * Render ASCII banner with gradient (static)
 */
export function renderBanner(): string {
  const lines: string[] = [];
  lines.push('');

  for (const line of ASCII_KLARVIDO) {
    lines.push('  ' + applyGradientToLine(line));
  }

  lines.push('');
  lines.push('  ' + color.gray('by ') + color.bold('Ordigita'));
  lines.push('  ' + color.underline(color.cyan('https://ordigita.pl')));
  lines.push('');

  return lines.join('\n');
}

/**
 * Print banner with smooth animation (no cursor tricks)
 */
export async function printBannerAnimated(options: { speed?: number } = {}): Promise<void> {
  const { speed = 20 } = options;

  // Hide cursor during animation
  process.stdout.write('\x1B[?25l');
  console.log('');

  // Phase 1: Animate "Klarvido" - character by character reveal per line
  for (let lineIdx = 0; lineIdx < ASCII_KLARVIDO.length; lineIdx++) {
    const line = ASCII_KLARVIDO[lineIdx];
    await printLineAnimated('  ' + line, speed);
  }

  // Phase 2: Subtitle with typewriter effect
  await sleep(150);
  console.log('');

  // "by Ordigita"
  process.stdout.write('  ');
  for (const char of 'by ') {
    process.stdout.write(color.gray(char));
    await sleep(30);
  }

  const companyText = 'Ordigita';
  for (let i = 0; i < companyText.length; i++) {
    const char = companyText[i];
    const progress = i / (companyText.length - 1);
    const rgb = interpolateColor(GRADIENT_START, GRADIENT_END, progress);
    process.stdout.write(`\x1b[1m${colorText(char, rgb)}`);
    await sleep(40);
  }
  console.log('');

  // URL
  await sleep(80);
  const url = 'https://ordigita.pl';
  process.stdout.write('  ');
  for (let i = 0; i < url.length; i++) {
    const progress = i / (url.length - 1);
    const rgb = interpolateColor(GRADIENT_START, GRADIENT_END, progress);
    process.stdout.write(`\x1b[4m${colorText(url[i], rgb)}`);
    await sleep(15);
  }
  process.stdout.write('\x1b[0m');
  console.log('');
  console.log('');

  // Show cursor again
  process.stdout.write('\x1B[?25h');
}

/**
 * Print a single line with character-by-character animation and gradient
 */
async function printLineAnimated(line: string, delay: number): Promise<void> {
  let charIndex = 0;
  const strippedLine = line.replace(/\s/g, '');
  const totalChars = strippedLine.length;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === ' ') {
      process.stdout.write(char);
    } else {
      const progress = charIndex / Math.max(totalChars - 1, 1);
      const rgb = interpolateColor(GRADIENT_START, GRADIENT_END, progress);
      process.stdout.write(colorText(char, rgb));
      charIndex++;
    }
  }
  console.log('');
  await sleep(delay);
}

/**
 * Print banner without animation (static)
 */
export function printBanner(): void {
  console.log(renderBanner());
}

/**
 * Simple sleep utility
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Render a simple divider line with gradient
 */
export function renderGradientDivider(width = 60): string {
  let output = '  ';
  for (let i = 0; i < width; i++) {
    const progress = i / Math.max(width - 1, 1);
    const rgb = interpolateColor(GRADIENT_START, GRADIENT_END, progress);
    output += colorText('─', rgb);
  }
  return output;
}
