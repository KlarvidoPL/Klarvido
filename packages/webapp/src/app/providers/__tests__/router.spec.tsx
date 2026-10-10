import { render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { Link } from 'react-router-dom';

import { RouterProvider } from '../router';

describe('RouterProvider scroll position', () => {
  const scrollToMock = jest.fn();
  let originalScrollTo: typeof window.scrollTo;

  beforeEach(() => {
    originalScrollTo = window.scrollTo;
    window.scrollTo = scrollToMock;
    scrollToMock.mockClear();
    window.history.replaceState(null, '', '/en/organizations');
  });

  afterEach(() => {
    window.scrollTo = originalScrollTo;
    window.history.replaceState(null, '', '/');
  });

  it('scrolls to the top when selecting an organization and navigating to another page', async () => {
    render(
      <RouterProvider>
        <Link to="/en/org-one">Select organization</Link>
        <Link to="/en/org-one/documents">Documents</Link>
        <Link to="/en/org-two">Switch organization</Link>
      </RouterProvider>
    );
    scrollToMock.mockClear();

    for (const label of ['Select organization', 'Documents', 'Switch organization']) {
      await userEvent.click(screen.getByRole('link', { name: label }));
      expect(scrollToMock).toHaveBeenLastCalledWith(0, 0);
    }
    expect(scrollToMock).toHaveBeenCalledTimes(3);
  });

  it('keeps the scroll position when only a query parameter changes', async () => {
    render(
      <RouterProvider>
        <Link to="/en/organizations?search=example">Filter organizations</Link>
      </RouterProvider>
    );
    scrollToMock.mockClear();

    await userEvent.click(screen.getByRole('link', { name: 'Filter organizations' }));
    expect(window.location.search).toBe('?search=example');
    expect(scrollToMock).not.toHaveBeenCalled();
  });
});
