/**
 * components/ui/Card.tsx
 * Generic glassmorphism info card used on the screening page.
 */

/**
 * Render an icon + title + body info card.
 *
 * @param icon Emoji shown above the title.
 * @param title Card heading.
 * @param children Body copy.
 */
export function Card({
  icon,
  title,
  children,
}: {
  icon: string;
  title: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <div className="info-card">
      <div className="info-icon" aria-hidden="true">{icon}</div>
      <h4>{title}</h4>
      <p>{children}</p>
    </div>
  );
}
