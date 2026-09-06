import path from 'path';
import { fileURLToPath } from 'url';

const trackerRoutes = [
  '/api/rooms',
  '/login',
  '/student-login',
  '/admin-login',
  '/register',
  '/verify-email',
  '/admin-2fa',
  '/withdraw-application',
  '/student-pending',
  '/student-approved',
  '/complete-profile',
  '/student-dashboard',
  '/student-complaint',
  '/mark-attendance',
  '/edit-profile',
  '/upload-profile-photo',
  '/upload-college-id',
  '/download-fee-receipt',
  '/download-college-id-card',
  '/generate-laundry-token',
  '/forgot-password',
  '/reset-password',
  '/logout',
  '/admin-dashboard',
  '/admin-action',
  '/admin-attendance-action',
  '/admin-attendance-save',
  '/mess-warden-login',
  '/mess-warden-dashboard',
  '/laundry-admin-login',
  '/laundry-admin-dashboard',
  '/laundry-verify',
  '/laundry-out-verify',
  '/laundry-pickup',
];

const projectRoot = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ['127.0.0.1', 'localhost'],
  turbopack: {
    root: projectRoot,
  },
  outputFileTracingRoot: projectRoot,
  async rewrites() {
    return trackerRoutes.map((route) => ({
      source: route,
  destination: `https://radha-krishna-hostel-new.onrender.com${route}`,
    }));
  },
};

export default nextConfig;
