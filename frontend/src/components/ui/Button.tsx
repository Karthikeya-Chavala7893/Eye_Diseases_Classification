/**
 * components/ui/Button.tsx
 * Design-system button reusing the legacy `.btn` classes.
 */

import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary';
  size?: 'md' | 'lg';
  children: ReactNode;
}

/**
 * Render a themed button.
 *
 * @param variant Visual weight — primary (filled) or secondary (outlined).
 * @param size Standard or large call-to-action sizing.
 */
export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  ...rest
}: ButtonProps): JSX.Element {
  const classes = ['btn', `btn-${variant}`, size === 'lg' ? 'btn-lg' : '', className]
    .filter(Boolean)
    .join(' ');
  return (
    <button className={classes} {...rest}>
      {children}
    </button>
  );
}
