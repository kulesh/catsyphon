/**
 * Tests for useRefreshCountdown hook.
 */

import { renderHook } from '@testing-library/react';
import { useRefreshCountdown } from './useRefreshCountdown';

describe('useRefreshCountdown', () => {
  it('should return seconds remaining until next refresh', () => {
    const now = Date.now();
    const refetchInterval = 15000; // 15 seconds

    const { result } = renderHook(() =>
      useRefreshCountdown(refetchInterval, now)
    );

    // Should start at 15 seconds
    expect(result.current).toBe(15);
  });

  it('should handle zero dataUpdatedAt', () => {
    const refetchInterval = 15000;

    const { result } = renderHook(() =>
      useRefreshCountdown(refetchInterval, 0)
    );

    // Should return 0 when dataUpdatedAt is 0
    expect(result.current).toBe(0);
  });

  it('should reset countdown when dataUpdatedAt changes', () => {
    const now = Date.now();
    const refetchInterval = 15000;

    const { result, rerender } = renderHook(
      ({ updatedAt }) => useRefreshCountdown(refetchInterval, updatedAt),
      { initialProps: { updatedAt: now } }
    );

    expect(result.current).toBe(15);

    // Simulate a refetch with new timestamp
    const newUpdatedAt = Date.now();
    rerender({ updatedAt: newUpdatedAt });

    // Should reset to 15 seconds
    expect(result.current).toBe(15);
  });
});
