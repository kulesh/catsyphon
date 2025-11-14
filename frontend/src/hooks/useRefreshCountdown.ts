/**
 * Hook for tracking time until next auto-refresh.
 * Returns seconds remaining until next refresh.
 */

import { useEffect, useState } from 'react';

export function useRefreshCountdown(
  refetchInterval: number,
  dataUpdatedAt: number
): number {
  const [secondsRemaining, setSecondsRemaining] = useState(0);

  useEffect(() => {
    if (!dataUpdatedAt) return;

    const updateCountdown = () => {
      const now = Date.now();
      const timeSinceLastUpdate = now - dataUpdatedAt;
      const timeUntilNext = refetchInterval - timeSinceLastUpdate;
      const seconds = Math.max(0, Math.ceil(timeUntilNext / 1000));
      setSecondsRemaining(seconds);
    };

    // Update immediately
    updateCountdown();

    // Update every 100ms for smooth countdown
    const interval = setInterval(updateCountdown, 100);

    return () => clearInterval(interval);
  }, [refetchInterval, dataUpdatedAt]);

  return secondsRemaining;
}
