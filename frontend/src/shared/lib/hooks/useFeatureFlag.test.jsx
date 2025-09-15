import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useFeatureFlag } from './useFeatureFlag';
import { useCurrentUser } from './useCurrentUser'; // Мы будем мокать этот хук

// Мокаем (подделываем) хук useCurrentUser, от которого зависит useFeatureFlag
vi.mock('./useCurrentUser', () => ({
  useCurrentUser: vi.fn(),
}));

describe('useFeatureFlag Hook', () => {
  it('должен возвращать true, если фича доступна', () => {
    // 1. Говорим, что useCurrentUser вернул пользователя с фичей 'scenarios'
    useCurrentUser.mockReturnValue({
      data: { available_features: ['scenarios', 'agency_mode'] },
    });

    // 2. Рендерим наш хук
    const { result } = renderHook(() => useFeatureFlag());

    // 3. Проверяем, что isFeatureAvailable('scenarios') возвращает true
    expect(result.current.isFeatureAvailable('scenarios')).toBe(true);
  });

  it('должен возвращать false, если фича НЕ доступна', () => {
    // 1. Говорим, что у пользователя нет фичи 'scenarios'
    useCurrentUser.mockReturnValue({
      data: { available_features: ['agency_mode'] },
    });

    // 2. Рендерим хук
    const { result } = renderHook(() => useFeatureFlag());

    // 3. Проверяем, что isFeatureAvailable('scenarios') возвращает false
    expect(result.current.isFeatureAvailable('scenarios')).toBe(false);
  });

  it('должен возвращать false, если данные пользователя еще не загружены', () => {
    // 1. Имитируем состояние загрузки (данных нет)
    useCurrentUser.mockReturnValue({
      data: undefined,
    });

    // 2. Рендерим хук
    const { result } = renderHook(() => useFeatureFlag());

    // 3. Проверяем, что он ничего не разрешает по умолчанию
    expect(result.current.isFeatureAvailable('scenarios')).toBe(false);
  });
});
