import { ReactNode } from 'react';
import { BrowserRouter } from 'react-router-dom';

import { useRouterScrollToTop } from '../../shared/hooks/useRouterScrollToTop';

const RouterScrollToTop = () => {
  useRouterScrollToTop();
  return null;
};

export const RouterProvider = ({ children }: { children: ReactNode }) => (
  <BrowserRouter>
    <RouterScrollToTop />
    {children}
  </BrowserRouter>
);
