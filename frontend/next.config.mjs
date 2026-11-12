/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  poweredByHeader: false,
  async redirects() {
    return ['attendance', 'schedule', 'reports'].map(section => ({
      source: '/' + section + '/:path*',
      destination: '/dashboard',
      permanent: false,
    }));
  },
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${process.env.API_PROXY_URL || 'http://127.0.0.1:8000'}/api/:path*` }];
  },
};
export default nextConfig;
