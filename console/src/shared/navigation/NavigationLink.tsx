import type { AnchorHTMLAttributes, MouseEvent } from "react";

import { useNavigation } from "./useNavigation";

interface NavigationLinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  to: string;
}

export function NavigationLink({ to, onClick, ...props }: NavigationLinkProps) {
  const { navigate } = useNavigation();

  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }
    event.preventDefault();
    navigate(to);
  };

  return <a {...props} href={to} onClick={handleClick} />;
}
