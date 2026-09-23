import React from 'react';
import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import posthog from 'posthog-js';

const navigate = vi.fn();
const auth = {
  signIn: vi.fn(),
  signInWithGoogle: vi.fn(),
  signInWithOtp: vi.fn(),
  verifyOtp: vi.fn(),
};

vi.mock('posthog-js', () => ({
  default: {
    capture: vi.fn(),
  },
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');

  return {
    ...actual,
    useNavigate: () => navigate,
    useLocation: () => ({ state: null }),
  };
});

vi.mock('../src/contexts/AuthContext', () => ({
  useAuth: () => auth,
}));

vi.mock('../src/components/SEO', () => ({
  SEO: () => null,
}));

vi.mock('../src/components/FallingBricks', () => ({
  default: () => null,
}));

vi.mock('../src/components/SiteFooter', () => ({
  SiteFooter: () => null,
}));

import LoginModal from '../src/components/LoginModal';
import LoginPage from '../src/pages/LoginPage';

function renderIntoBody(node: React.ReactNode) {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);

  act(() => {
    root.render(node);
  });

  return {
    container,
    unmount: () => {
      act(() => {
        root.unmount();
      });
      container.remove();
    },
  };
}

function findButton(container: HTMLElement, label: string) {
  return Array.from(container.querySelectorAll('button')).find(
    (button) => button.textContent?.trim() === label,
  ) as HTMLButtonElement | undefined;
}

function changeInput(input: HTMLInputElement, value: string) {
  const valueSetter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    'value',
  )?.set;

  act(() => {
    valueSetter?.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });
}

describe('login auth options', () => {
  beforeEach(() => {
    auth.signIn.mockResolvedValue({ error: null });
    auth.signInWithGoogle.mockResolvedValue({ error: null });
    auth.signInWithOtp.mockResolvedValue({ error: null });
    auth.verifyOtp.mockResolvedValue({ error: null });
    navigate.mockReset();
    vi.mocked(posthog.capture).mockClear();
    Object.defineProperty(window, 'scrollTo', {
      value: vi.fn(),
      writable: true,
    });
  });

  it('keeps the modal on the email flow by default and exposes a password toggle', () => {
    const { container, unmount } = renderIntoBody(
      <LoginModal open onClose={() => undefined} />,
    );

    try {
      expect(container.textContent).toContain('Enter email to login or sign-up.');
      expect(container.textContent).toContain('Continue with magic link');
      expect(container.querySelector('input[type="password"]')).toBeNull();

      const toggle = findButton(container, 'Use password');
      expect(toggle).toBeDefined();

      act(() => {
        toggle?.click();
      });

      expect(container.querySelector('input[type="password"]')).not.toBeNull();
      expect(container.textContent).toContain('Use your email and password to sign in.');
      expect(posthog.capture).toHaveBeenCalledWith('auth_method_selected', {
        surface: 'login_modal',
        method: 'password',
      });
    } finally {
      unmount();
    }
  });

  it('submits password sign-in from the modal', async () => {
    const onSuccess = vi.fn();
    const { container, unmount } = renderIntoBody(
      <LoginModal open onClose={() => undefined} onSuccess={onSuccess} />,
    );

    try {
      act(() => {
        findButton(container, 'Use password')?.click();
      });

      const emailInput = container.querySelector('input[type="email"]') as HTMLInputElement;
      const passwordInput = container.querySelector('input[type="password"]') as HTMLInputElement;
      const form = container.querySelector('form') as HTMLFormElement;

      changeInput(emailInput, 'builder@example.com');
      changeInput(passwordInput, 'secret-password');

      await act(async () => {
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });

      expect(auth.signIn).toHaveBeenCalledWith('builder@example.com', 'secret-password');
      expect(onSuccess).toHaveBeenCalledOnce();
      expect(localStorage.getItem('remember_email')).toBe('builder@example.com');
      expect(posthog.capture).toHaveBeenCalledWith('auth_password_login_submitted', {
        surface: 'login_modal',
        method: 'password',
      });
    } finally {
      unmount();
    }
  });

  it('lets the login page switch to password sign-in and navigate after success', async () => {
    const { container, unmount } = renderIntoBody(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    try {
      expect(container.textContent).toContain('Enter email to login or sign-up.');

      act(() => {
        findButton(container, 'Use password')?.click();
      });

      const emailInput = container.querySelector('input[type="email"]') as HTMLInputElement;
      const passwordInput = container.querySelector('input[type="password"]') as HTMLInputElement;

      changeInput(emailInput, 'reviewer@example.com');
      changeInput(passwordInput, 'app-store-password');
      const form = container.querySelector('form') as HTMLFormElement;

      await act(async () => {
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });

      expect(auth.signIn).toHaveBeenCalledWith('reviewer@example.com', 'app-store-password');
      expect(navigate).toHaveBeenCalledWith('/dashboard');
      expect(posthog.capture).toHaveBeenCalledWith('auth_method_selected', {
        surface: 'login_page',
        method: 'password',
      });
    } finally {
      unmount();
    }
  });
});
