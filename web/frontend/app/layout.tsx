import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'FaceCam — Chấm công', description: 'Không gian quản lý chấm công, nhân sự và lịch làm việc.' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="vi"><body>{children}</body></html>;
}
