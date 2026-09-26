import { Helmet } from 'react-helmet-async';

export const KlarvidoApp = () => (
  <div className="fixed inset-0 z-[70] bg-[#f7f9fc]">
    <Helmet title="Klarvido" />
    <iframe
      title="Klarvido"
      src="/klarvido/mockup.html#/today"
      className="h-full w-full border-0"
      allow="clipboard-write"
    />
  </div>
);
