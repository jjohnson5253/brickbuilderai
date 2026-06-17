/**
 * LDraw object packer utility
 * Converts .ldr files to .mpd format for Three.js LDrawLoader
 */

interface PackingResult {
  packedContent: string;
  success: boolean;
  error?: string;
}

export class LDrawPacker {
  private static readonly MATERIALS_CONTENT = `0 LDraw.org Configuration File
0 Name: LDConfig.ldr
0 Author: LDraw.org
0 !LDRAW_ORG Configuration UPDATE 2019-12-03
0 
0 // LEGO colour palette
0 // Colour values from LEGO
0 !COLOUR Black                     CODE   0   VALUE #05131D   EDGE #595959
0 !COLOUR Blue                      CODE   1   VALUE #0055BF   EDGE #333333
0 !COLOUR Green                     CODE   2   VALUE #257A3E   EDGE #333333
0 !COLOUR Dark_Turquoise            CODE   3   VALUE #00838F   EDGE #333333
0 !COLOUR Red                       CODE   4   VALUE #C91A09   EDGE #333333
0 !COLOUR Dark_Pink                 CODE   5   VALUE #C870A0   EDGE #333333
0 !COLOUR Brown                     CODE   6   VALUE #583927   EDGE #1E1E1E
0 !COLOUR Light_Gray                CODE   7   VALUE #9BA19D   EDGE #333333
0 !COLOUR Dark_Gray                 CODE   8   VALUE #6D6E5C   EDGE #1E1E1E
0 !COLOUR Light_Blue                CODE   9   VALUE #B4D2E3   EDGE #333333
0 !COLOUR Bright_Green              CODE  10   VALUE #4B9F4A   EDGE #333333
0 !COLOUR Light_Turquoise           CODE  11   VALUE #55A5AF   EDGE #333333
0 !COLOUR Salmon                    CODE  12   VALUE #F2705E   EDGE #333333
0 !COLOUR Pink                      CODE  13   VALUE #FC97AC   EDGE #333333
0 !COLOUR Yellow                    CODE  14   VALUE #F2CD37   EDGE #333333
0 !COLOUR White                     CODE  15   VALUE #FFFFFF   EDGE #333333`;

  static async packLDrawContent(ldrContent: string, fileName: string = 'model.ldr'): Promise<PackingResult> {
    try {
      const objectsPaths: string[] = [];
      const objectsContents: string[] = [];
      const pathMap: { [key: string]: string } = {};
      const listOfNotFound: string[] = [];

      // Parse the main object
      const mainObjectResult = this.parseObject(ldrContent, fileName, true, pathMap, objectsPaths, objectsContents, listOfNotFound);
      
      if (!mainObjectResult.success) {
        return {
          packedContent: '',
          success: false,
          error: mainObjectResult.error
        };
      }

      // Since we're working with a single LDR file from the API, we don't need to resolve external references
      // Just pack the main content with materials

      let packedContent = this.MATERIALS_CONTENT + '\n\n';
      
      // Add all processed objects in reverse order (dependencies first)
      for (let i = objectsContents.length - 1; i >= 0; i--) {
        packedContent += objectsContents[i] + '\n';
      }

      return {
        packedContent,
        success: true
      };
    } catch (error) {
      return {
        packedContent: '',
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred'
      };
    }
  }

  private static parseObject(
    objectContent: string,
    fileName: string,
    isRoot: boolean,
    pathMap: { [key: string]: string },
    objectsPaths: string[],
    objectsContents: string[],
    listOfNotFound: string[]
  ): { success: boolean; error?: string } {
    try {
      // Normalize line endings
      if (objectContent.indexOf('\r\n') !== -1) {
        objectContent = objectContent.replace(/\r\n/g, '\n');
      }

      let processedObjectContent = isRoot ? '' : `0 FILE ${fileName}\n`;
      const lines = objectContent.split('\n');

      for (let i = 0; i < lines.length; i++) {
        let line = lines[i];
        
        // Skip leading whitespace
        line = line.trimStart();
        
        if (!line) {
          processedObjectContent += '\n';
          continue;
        }

        // Handle FILE directives for embedded objects
        if (line.startsWith('0 FILE ')) {
          if (i === 0 && !isRoot) {
            // Skip first line FILE meta directive for non-root objects
            continue;
          }

          const subobjectFileName = line.substring(7).trim().replace(/\\/g, '/');
          if (subobjectFileName && !pathMap[subobjectFileName]) {
            pathMap[subobjectFileName] = subobjectFileName;
          }
        }

        // Handle subobject references (type 1 lines)
        if (line.startsWith('1 ')) {
          const parts = line.split(/\s+/);
          if (parts.length >= 15) {
            // Extract subobject filename (last part)
            const subobjectFileName = parts.slice(14).join(' ').trim().replace(/\\/g, '/');
            
            if (subobjectFileName) {
              // For this implementation, we'll just keep the reference as-is
              // In a full implementation, you'd recursively load and process subobjects
              if (!pathMap[subobjectFileName]) {
                pathMap[subobjectFileName] = subobjectFileName;
              }
              
              // Reconstruct the line with the mapped path
              const lineStart = parts.slice(0, 14).join(' ');
              processedObjectContent += `${lineStart} ${pathMap[subobjectFileName]}\n`;
            } else {
              processedObjectContent += line + '\n';
            }
          } else {
            processedObjectContent += line + '\n';
          }
        } else {
          processedObjectContent += line + '\n';
        }
      }

      // Add to collections if not already present
      if (objectsPaths.indexOf(fileName) < 0) {
        objectsPaths.push(fileName);
        objectsContents.push(processedObjectContent);
      }

      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown parsing error'
      };
    }
  }

  /**
   * Convert LDR content to packed MPD format suitable for Three.js LDrawLoader
   */
  static async convertLdrToMpd(ldrContent: string, modelName: string = 'generated_model'): Promise<string> {
    const result = await this.packLDrawContent(ldrContent, `${modelName}.ldr`);
    
    if (!result.success) {
      throw new Error(result.error || 'Failed to pack LDR content');
    }
    
    return result.packedContent;
  }
}