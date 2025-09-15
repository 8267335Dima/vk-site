import React from 'react';
import { Box, Grid, Typography, Divider, MenuItem } from '@mui/material';
import { useFormContext } from 'react-hook-form';

import { content } from '@/shared/config/content';
import PresetManager from '../PresetManager';

import { SwitchField } from './fields/SwitchField';
import { SelectField } from './fields/SelectField';
import { TextField } from './fields/TextField';
import { LabelWithTooltip } from './fields/LabelWithTooltip';

export const CommonFiltersSettings = ({ actionKey }) => {
  const showClosedProfilesFilter = [
    'accept_friends',
    'add_recommended',
    'mass_messaging',
  ].includes(actionKey);
  const isAcceptFriends = actionKey === 'accept_friends';

  return (
    <Box>
      <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>
        {content.modal.filtersTitle}
      </Typography>
      <Grid container spacing={2} alignItems="center">
        <Grid item xs={12} sm={6}>
          <SwitchField name="filters.is_online" label="Только онлайн" />
        </Grid>
        {showClosedProfilesFilter && (
          <Grid item xs={12} sm={6}>
            <SwitchField
              name="filters.allow_closed_profiles"
              label={
                <LabelWithTooltip
                  title="Закрытые профили"
                  tooltipText="Разрешить взаимодействие с пользователями, у которых закрыт профиль. Часть фильтров (статус, кол-во друзей) не будет применяться."
                />
              }
            />
          </Grid>
        )}
        <Grid item xs={12}>
          {/* --- ИСПРАВЛЕНИЕ ЗДЕСЬ --- */}
          <SelectField
            name="filters.last_seen_hours"
            label="Был(а) в сети"
            defaultValue={''}
          >
            <MenuItem value={''}>
              <em>Неважно</em>
            </MenuItem>
            <MenuItem value={1}>В течение часа</MenuItem>
            <MenuItem value={3}>В течение 3 часов</MenuItem>
            <MenuItem value={12}>В течение 12 часов</MenuItem>
            <MenuItem value={24}>В течение суток</MenuItem>
          </SelectField>
        </Grid>
        <Grid item xs={12}>
          <SelectField name="filters.sex" label="Пол" defaultValue={0}>
            <MenuItem value={0}>Любой</MenuItem>
            <MenuItem value={1}>Женский</MenuItem>
            <MenuItem value={2}>Мужской</MenuItem>
          </SelectField>
        </Grid>
        <Grid item xs={12}>
          <TextField
            name="filters.status_keyword"
            label="Ключевое слово в статусе"
            placeholder="Например: ищу работу, спб"
          />
        </Grid>
        {isAcceptFriends && (
          <>
            <Grid item xs={6}>
              <TextField
                name="filters.min_friends"
                label="Мин. друзей"
                type="number"
                helperText="Оставьте пустым, чтобы не использовать"
              />
            </Grid>
            <Grid item xs={6}>
              <TextField
                name="filters.max_friends"
                label="Макс. друзей"
                type="number"
                helperText="Оставьте пустым, чтобы не использовать"
              />
            </Grid>
            <Grid item xs={6}>
              <TextField
                name="filters.min_followers"
                label="Мин. подписчиков"
                type="number"
                helperText="Оставьте пустым, чтобы не использовать"
              />
            </Grid>
            <Grid item xs={6}>
              <TextField
                name="filters.max_followers"
                label="Макс. подписчиков"
                type="number"
                helperText="Оставьте пустым, чтобы не использовать"
              />
            </Grid>
          </>
        )}
      </Grid>
    </Box>
  );
};

export const RemoveFriendsFilters = () => {
  return (
    <Box>
      <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>
        Критерии для чистки
      </Typography>
      <Grid container spacing={2} alignItems="center">
        <Grid item xs={12}>
          <SwitchField
            name="filters.remove_banned"
            defaultValue={true}
            label={
              <LabelWithTooltip
                title="Удаленные / забаненные"
                tooltipText="Удалить пользователей, чьи страницы были удалены или заблокированы."
              />
            }
          />
        </Grid>
        <Grid item xs={12}>
          {/* --- ИСПРАВЛЕНИЕ ЗДЕСЬ --- */}
          <SelectField
            name="filters.last_seen_days"
            label="Неактивные (не заходили более)"
            defaultValue={''}
          >
            <MenuItem value={''}>
              <em>Не удалять по неактивности</em>
            </MenuItem>
            <MenuItem value={30}>1 месяца</MenuItem>
            <MenuItem value={90}>3 месяцев</MenuItem>
            <MenuItem value={180}>6 месяцев</MenuItem>
            <MenuItem value={365}>1 года</MenuItem>
          </SelectField>
        </Grid>
        <Grid item xs={12}>
          <SelectField name="filters.sex" label="Пол" defaultValue={0}>
            <MenuItem value={0}>Любой</MenuItem>
            <MenuItem value={1}>Женский</MenuItem>
            <MenuItem value={2}>Мужской</MenuItem>
          </SelectField>
        </Grid>
      </Grid>
    </Box>
  );
};

const KeywordFilter = ({ title, name, placeholder, helperText }) => (
  <Box>
    <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>
      {title}
    </Typography>
    <TextField
      name={name}
      label="Ключевое слово или фраза"
      placeholder={placeholder}
      helperText={helperText}
    />
  </Box>
);

export const ActionModalFilters = ({ actionKey }) => {
  const { getValues, reset } = useFormContext();

  const onApplyPreset = (filters) => {
    const currentValues = getValues();
    reset({
      ...currentValues,
      filters: filters,
    });
  };

  let FilterComponent;
  switch (actionKey) {
    case 'remove_friends':
      FilterComponent = <RemoveFriendsFilters />;
      break;
    case 'leave_groups':
      FilterComponent = (
        <KeywordFilter
          title="Критерии для отписки"
          name="filters.status_keyword"
          placeholder="Например: барахолка, новости"
          helperText="Оставьте пустым, чтобы отписываться от всех подряд."
        />
      );
      break;
    case 'join_groups':
      FilterComponent = (
        <KeywordFilter
          title="Критерии для вступления"
          name="filters.status_keyword"
          placeholder="Например: SMM, дизайн, маркетинг"
          helperText="Введите ключевые слова для поиска релевантных групп."
        />
      );
      break;
    default:
      FilterComponent = <CommonFiltersSettings actionKey={actionKey} />;
  }

  return (
    <Box>
      <PresetManager
        actionKey={actionKey}
        onApply={onApplyPreset}
        currentFilters={getValues('filters')}
      />
      <Divider sx={{ my: 2 }} />
      {FilterComponent}
    </Box>
  );
};
