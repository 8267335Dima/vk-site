import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useForm, FormProvider } from 'react-hook-form';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ActionModal from './ActionModal';
import { content } from '@/shared/config/content';

// Мокаем хуки и API
vi.mock('@/shared/lib/hooks/useCurrentUser', () => ({
  useCurrentUser: () => ({
    data: { daily_add_friends_limit: 40, daily_likes_limit: 1000 },
  }),
}));
vi.mock('@/shared/lib/hooks/useActionTask', () => ({
  useActionTask: () => ({ mutate: vi.fn(), isLoading: false }),
}));
vi.mock('@/shared/api/api', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    fetchTaskInfo: vi.fn().mockResolvedValue({ count: 10 }),
    fetchFilterPresets: vi.fn().mockResolvedValue([]),
  };
});

const TestWrapper = ({ children }) => {
  const methods = useForm();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>
      <FormProvider {...methods}>{children}</FormProvider>
    </QueryClientProvider>
  );
};

describe('ActionModal Component', () => {
  it('должен рендерить правильные поля для actionKey="like_feed"', async () => {
    const actionKey = 'like_feed';
    const config = content.automations.find((a) => a.id === actionKey);
    const title = config.modalTitle;
    const sliderLabel = config.modal_count_label;

    render(
      <TestWrapper>
        <ActionModal
          open={true}
          onClose={() => {}}
          actionKey={actionKey}
          title={title}
        />
      </TestWrapper>
    );

    expect(await screen.findByText(title)).toBeInTheDocument();
    expect(await screen.findByText(sliderLabel)).toBeInTheDocument();
    expect(
      await screen.findByText('Лайкать только посты с фото')
    ).toBeInTheDocument();
  });

  it('должен рендерить правильные поля для actionKey="add_recommended"', async () => {
    const actionKey = 'add_recommended';
    const config = content.automations.find((a) => a.id === actionKey);
    const title = config.modalTitle;
    const sliderLabel = config.modal_count_label;

    render(
      <TestWrapper>
        <ActionModal
          open={true}
          onClose={() => {}}
          actionKey={actionKey}
          title={title}
        />
      </TestWrapper>
    );

    expect(await screen.findByText(title)).toBeInTheDocument();
    expect(await screen.findByText(sliderLabel)).toBeInTheDocument();
    expect(await screen.findByText('Лайк после заявки')).toBeInTheDocument();
    expect(
      await screen.findByText('Сообщение при добавлении')
    ).toBeInTheDocument();
  });
});
