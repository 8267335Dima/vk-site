import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  CircularProgress,
  Stack,
  Divider,
  Typography,
  ToggleButtonGroup,
  ToggleButton,
  RadioGroup,
  FormControlLabel,
  Radio,
} from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';

import { updateAutomation } from '@/shared/api/api';
import {
  CommonFiltersSettings,
  RemoveFriendsFilters,
} from './ActionModal/ActionModalFilters';
import CountSlider from '@/shared/ui/CountSlider/CountSlider';
import { content } from '@/shared/config/content';
import { useCurrentUser } from '@/shared/lib/hooks/useCurrentUser';

const EternalOnlineSettings = ({ settings, onChange }) => {
  const days = [
    { key: 0, label: 'Пн' },
    { key: 1, label: 'Вт' },
    { key: 2, label: 'Ср' },
    { key: 3, label: 'Чт' },
    { key: 4, label: 'Пт' },
    { key: 5, label: 'Сб' },
    { key: 6, label: 'Вс' },
  ];

  const handleDaysChange = (event, newDays) => {
    onChange('days_of_week', newDays);
  };

  return (
    <Stack spacing={2}>
      <Typography variant="subtitle1" fontWeight={600}>
        Режим работы
      </Typography>
      <RadioGroup
        row
        value={settings.schedule_type || 'always'}
        onChange={(e) => onChange('schedule_type', e.target.value)}
      >
        <FormControlLabel
          value="always"
          control={<Radio />}
          label="Круглосуточно"
        />
        <FormControlLabel
          value="custom"
          control={<Radio />}
          label="По расписанию"
        />
      </RadioGroup>

      {settings.schedule_type === 'custom' && (
        <Stack
          spacing={2}
          p={2}
          borderRadius={2}
          border="1px solid"
          borderColor="divider"
        >
          <Typography variant="body2" color="text.secondary">
            Выберите дни и время (по МСК), когда статус &quot;онлайн&quot; будет
            активен.
          </Typography>
          <ToggleButtonGroup
            value={settings.days_of_week || []}
            onChange={handleDaysChange}
            aria-label="дни недели"
            fullWidth
          >
            {days.map((day) => (
              <ToggleButton key={day.key} value={day.key} sx={{ flexGrow: 1 }}>
                {day.label}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
          <Stack direction="row" spacing={2}>
            <TextField
              label="Начало"
              type="time"
              value={settings.start_time || '09:00'}
              onChange={(e) => onChange('start_time', e.target.value)}
              fullWidth
              InputLabelProps={{ shrink: true }}
            />
            <TextField
              label="Конец"
              type="time"
              value={settings.end_time || '21:00'}
              onChange={(e) => onChange('end_time', e.target.value)}
              fullWidth
              InputLabelProps={{ shrink: true }}
            />
          </Stack>
        </Stack>
      )}
    </Stack>
  );
};

const AutomationSettingsModal = ({ open, onClose, automation }) => {
  const queryClient = useQueryClient();
  const [settings, setSettings] = useState({});
  const { data: userInfo } = useCurrentUser();

  useEffect(() => {
    if (open && automation) {
      const defaults = {
        count: 50,
        filters: {
          sex: 0,
          is_online: false,
          allow_closed_profiles: false,
          remove_banned: true,
          last_seen_hours: null,
          last_seen_days: null,
          min_friends: null,
          max_friends: null,
          min_followers: null,
          max_followers: null,
        },
        message_template_default:
          'С Днем Рождения, {name}! Желаю всего самого наилучшего, успехов и ярких моментов в жизни.',
        schedule_type: 'always',
        start_time: '09:00',
        end_time: '21:00',
        days_of_week: [0, 1, 2, 3, 4],
      };
      setSettings({ ...defaults, ...(automation.settings || {}) });
    }
  }, [open, automation]);

  const mutation = useMutation({
    mutationFn: updateAutomation,
    onSuccess: (updatedAutomation) => {
      queryClient.setQueryData(['automations'], (oldData) =>
        oldData.map((a) =>
          a.automation_type === updatedAutomation.automation_type
            ? updatedAutomation
            : a
        )
      );
      toast.success(`Настройки для "${updatedAutomation.name}" сохранены!`);
      onClose();
    },
    onError: (error) =>
      toast.error(error.response?.data?.detail || 'Ошибка сохранения'),
  });

  const handleSettingsChange = (name, value) => {
    if (name.startsWith('filters.')) {
      const filterName = name.split('.')[1];
      setSettings((s) => ({
        ...s,
        filters: { ...(s.filters || {}), [filterName]: value },
      }));
    } else {
      setSettings((s) => ({ ...s, [name]: value }));
    }
  };

  const handleSave = () => {
    mutation.mutate({
      automationType: automation.automation_type,
      isActive: automation.is_active,
      settings: settings,
    });
  };

  if (!automation) return null;

  const automationConfig = content.automations.find(
    (a) => a.id === automation.automation_type
  );
  const needsCount = automationConfig?.has_count_slider;
  const needsFilters = automationConfig?.has_filters;

  const getLimit = () => {
    if (automation.automation_type.includes('add'))
      return userInfo?.daily_add_friends_limit || 100;
    if (automation.automation_type.includes('like'))
      return userInfo?.daily_likes_limit || 1000;
    return 1000;
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle sx={{ fontWeight: 600 }}>
        Настройки: {automation.name}
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={3} py={2}>
          <Typography variant="body2" color="text.secondary">
            Здесь вы можете задать параметры для автоматического выполнения
            задачи. Настройки сохраняются для каждого действия индивидуально.
          </Typography>

          {automation.automation_type === 'birthday_congratulation' && (
            <TextField
              multiline
              rows={4}
              label="Шаблон поздравления"
              name="message_template_default"
              value={settings.message_template_default || ''}
              onChange={(e) =>
                handleSettingsChange(e.target.name, e.target.value)
              }
              helperText="Используйте {name} для подстановки имени друга."
            />
          )}

          {automation.automation_type === 'eternal_online' && (
            <EternalOnlineSettings
              settings={settings}
              onChange={handleSettingsChange}
            />
          )}

          {needsCount && (
            <CountSlider
              label={automationConfig.modal_count_label}
              value={settings.count || 20}
              onChange={(val) => handleSettingsChange('count', val)}
              max={getLimit()}
            />
          )}

          {needsFilters && <Divider />}

          {needsFilters && automation.automation_type === 'remove_friends' && (
            <RemoveFriendsFilters
              filters={settings.filters || {}}
              onChange={(name, val) =>
                handleSettingsChange(`filters.${name}`, val)
              }
            />
          )}
          {needsFilters &&
            !['remove_friends'].includes(automation.automation_type) && (
              <CommonFiltersSettings
                filters={settings.filters || {}}
                onChange={(name, val) =>
                  handleSettingsChange(`filters.${name}`, val)
                }
                actionKey={automation.automation_type}
              />
            )}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ p: 2 }}>
        <Button onClick={onClose}>Отмена</Button>
        <Button
          onClick={handleSave}
          variant="contained"
          disabled={mutation.isLoading}
        >
          {mutation.isLoading ? <CircularProgress size={24} /> : 'Сохранить'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default AutomationSettingsModal;
