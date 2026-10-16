import {defineConfig} from 'vite';
import macros from 'unplugin-parcel-macros';
export default defineConfig({plugins:[macros.vite()],build:{target:'es2022',cssMinify:'lightningcss',cssTarget:'chrome110',rollupOptions:{output:{manualChunks(id){if(/macro-(.*)\.css$/.test(id)||/@react-spectrum\/s2\/.*\.css$/.test(id))return 's2-styles';}}}}});
