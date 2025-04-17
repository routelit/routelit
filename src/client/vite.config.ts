import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'
import dts from 'vite-plugin-dts'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  // Set the third parameter to '' to load all env regardless of the `VITE_` prefix.
  const env = loadEnv(mode, process.cwd(), '')

  const isLibraryBuild = env.BUILD_TARGET === 'lib';

  const baseConfig = {
    plugins: [react()],
    // Set base path for all asset URLs
    // base: '/routelit_assets/',
    server: {
      cors: true,
      // Important: Allow requests from Flask server
      headers: {
        'Access-Control-Allow-Origin': '*'
      }
    },
    resolve: {
      extensions: ['.mjs', '.js', '.mts', '.ts', '.jsx', '.tsx', '.json'], // Ensure proper file extensions
    }
  };

  if (isLibraryBuild) {
    // Library build configuration
    return {
      ...baseConfig,
      plugins: [
        ...baseConfig.plugins,
        dts({
          include: ["src/**/*.ts", "src/**/*.tsx", "src/**/*.d.ts"],
          outDir: "dist",
          rollupTypes: true,
        })
      ],
      build: {
        lib: {
          // Could also be a dictionary or array of multiple entry points
          entry: resolve(__dirname, 'src/client.ts'),
          name: 'RoutelitClient', // The global variable name when used in UMD builds
          // the proper extensions will be added
          fileName: (format) => `routelit-client.${format}.js`
        },
        rollupOptions: {
          // make sure to externalize deps that shouldn't be bundled
          // into your library
          external: ['react', 'react-dom', 'react/jsx-runtime'], // Added jsx-runtime
          output: {
            // Provide global variables to use in the UMD build
            // for externalized deps
            globals: {
              'react': 'React',
              'react-dom': 'ReactDOM',
              'react/jsx-runtime': 'jsxRuntime',
              './src/client.ts': 'RoutelitClient'
            }
          }
        },
        outDir: 'dist',
        // emptyOutDir: true,
      }
    };
  } else {
    // Default build configuration (for Flask integration)
    return {
      ...baseConfig,
      build: {
        // Relative path from this file to the Flask static directory
        outDir: '../routelit/static',
        emptyOutDir: true,
        // Generate manifest for Flask to reference assets
        manifest: true,
        rollupOptions: {
          // Make the vendor a separate entry
          input: {
            app: resolve(__dirname, 'src/main.tsx')
          },
        }
      }
    };
  }
})
