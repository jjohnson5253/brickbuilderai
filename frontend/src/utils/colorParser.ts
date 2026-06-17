/**
 * LDraw Color Parser Utility
 * Extracts color definitions from MPD content and provides color name lookups
 */

export interface LDrawColor {
  code: number;
  name: string;
  value: string; // Hex color value
  edge: string;  // Edge color
}

/**
 * Parses LDraw color definitions from MPD content
 * @param mpdContent - The MPD file content containing color definitions
 * @returns Map of color code to color info
 */
export function parseLDrawColors(mpdContent: string): Map<number, LDrawColor> {
  const colorMap = new Map<number, LDrawColor>();
  
  // Split content into lines
  const lines = mpdContent.split('\n');
  
  for (const line of lines) {
    // Look for color definition lines like:
    // 0 !COLOUR Black                     CODE   0   VALUE #1B2A34   EDGE #808080
    if (line.includes('!COLOUR') && line.includes('CODE') && line.includes('VALUE')) {
      try {
        // Extract color name (between !COLOUR and CODE)
        const colorMatch = line.match(/!COLOUR\s+([^\s]+)/);
        if (!colorMatch) continue;
        
        const colorName = colorMatch[1].replace(/_/g, ' '); // Replace underscores with spaces
        
        // Extract color code
        const codeMatch = line.match(/CODE\s+(\d+)/);
        if (!codeMatch) continue;
        
        const colorCode = parseInt(codeMatch[1], 10);
        
        // Extract color value (hex)
        const valueMatch = line.match(/VALUE\s+(#[A-Fa-f0-9]{6})/);
        if (!valueMatch) continue;
        
        const colorValue = valueMatch[1];
        
        // Extract edge color (optional)
        const edgeMatch = line.match(/EDGE\s+(#[A-Fa-f0-9]{6})/);
        const edgeColor = edgeMatch ? edgeMatch[1] : colorValue;
        
        // Add to map
        colorMap.set(colorCode, {
          code: colorCode,
          name: colorName,
          value: colorValue,
          edge: edgeColor
        });
        
      } catch (error) {
        console.warn('Failed to parse color line:', line, error);
      }
    }
  }
  
  //console.log(`Parsed ${colorMap.size} LDraw colors from MPD content`);
  return colorMap;
}

/**
 * Gets a human-readable color name for a color code
 * @param colorCode - The LDraw color code
 * @param colorMap - Map of color codes to color info
 * @returns Human-readable color name or fallback
 */
export function getColorName(colorCode: number, colorMap: Map<number, LDrawColor>): string {
  const color = colorMap.get(colorCode);
  if (color) {
    return color.name;
  }
  
  // Fallback to color code if not found
  return `Color ${colorCode}`;
}

/**
 * Fallback color names for common LDraw colors (in case parsing fails)
 */
export const FALLBACK_COLORS: Record<number, string> = {
  0: 'Black',
  1: 'Blue', 
  2: 'Green',
  3: 'Dark Turquoise',
  4: 'Red',
  5: 'Dark Pink',
  6: 'Brown',
  7: 'Light Gray',
  8: 'Dark Gray',
  9: 'Light Blue',
  10: 'Bright Green',
  11: 'Light Turquoise',
  12: 'Light Red',
  13: 'Pink',
  14: 'Yellow',
  15: 'White',
  16: 'Light Green',
  17: 'Light Yellow',
  18: 'Tan',
  19: 'Light Violet',
  20: 'Purple',
  21: 'Bright Purple',
  22: 'Magenta',
  23: 'Lime',
  24: 'Dark Tan',
  25: 'Orange',
  26: 'Maroon',
  27: 'Light Pink',
  28: 'Dark Green',
  29: 'Medium Green',
  30: 'Medium Blue'
};

/**
 * Gets color name with fallback support
 * @param colorCode - The LDraw color code
 * @param colorMap - Map of color codes to color info (optional)
 * @returns Human-readable color name
 */
export function getColorNameWithFallback(colorCode: number, colorMap?: Map<number, LDrawColor>): string {
  // Try parsed colors first
  if (colorMap) {
    const color = colorMap.get(colorCode);
    if (color) {
      return color.name;
    }
  }
  
  // Try fallback colors
  if (FALLBACK_COLORS[colorCode]) {
    return FALLBACK_COLORS[colorCode];
  }
  
  // Final fallback
  return `Color ${colorCode}`;
}