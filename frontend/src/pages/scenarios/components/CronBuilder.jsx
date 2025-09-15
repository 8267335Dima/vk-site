import React, { useState, useEffect } from 'react';
import {
  TextField,
  Paper,
  Typography,
  Grid,
  ToggleButtonGroup,
  ToggleButton,
} from '@mui/material';
import cronstrue from 'cronstrue/i18n';

export const CronBuilder = ({ schedule, setSchedule }) => {
  const parseCron = (cron) => {
    try {
      const [minute, hour, , , dayOfWeek] = cron.split(' ');
      return { minute, hour, dayOfWeek };
    } catch {
      return { minute: '0', hour: '9', dayOfWeek: '1,2,3,4,5' };
    }
  };

  const [cronParts, setCronParts] = useState(parseCron(schedule));

  useEffect(() => {
    const { minute, hour, dayOfWeek } = cronParts;
    setSchedule(`${minute} ${hour} * * ${dayOfWeek}`);
  }, [cronParts, setSchedule]);

  const handleTimeChange = (e) => {
    const [hour, minute] = e.target.value.split(':');
    setCronParts((p) => ({ ...p, hour: hour || '0', minute: minute || '0' }));
  };

  const handleDaysChange = (event, newDays) => {
    if (newDays.length) {
      setCronParts((p) => ({ ...p, dayOfWeek: newDays.join(',') }));
    }
  };

  const weekDays = [
    { key: '1', label: 'Пн' },
    { key: '2', label: 'Вт' },
    { key: '3', label: 'Ср' },
    { key: '4', label: 'Чт' },
    { key: '5', label: 'Пт' },
    { key: '6', label: 'Сб' },
    { key: '0', label: 'Вс' },
  ];

  return (
    <Paper variant="outlined" sx={{ p: 2.5, bgcolor: 'transparent' }}>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Расписание запуска
      </Typography>
      <Grid container spacing={2} alignItems="center">
        <Grid item xs={12} sm={4}>
          <TextField
            label="Время запуска (МСК)"
            type="time"
            value={`${(cronParts.hour || '09').padStart(2, '0')}:${(
              cronParts.minute || '00'
            ).padStart(2, '0')}`}
            onChange={handleTimeChange}
            fullWidth
            InputLabelProps={{ shrink: true }}
          />
        </Grid>
        <Grid item xs={12} sm={8}>
          <ToggleButtonGroup
            value={cronParts.dayOfWeek.split(',')}
            onChange={handleDaysChange}
            aria-label="дни недели"
            fullWidth
          >
            {weekDays.map((day) => (
              <ToggleButton key={day.key} value={day.key} sx={{ flexGrow: 1 }}>
                {day.label}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
        </Grid>
        <Grid item xs={12}>
          <Typography variant="body2" color="text.secondary">
            {cronstrue.toString(schedule, { locale: 'ru' })}
          </Typography>
        </Grid>
      </Grid>
    </Paper>
  );
};
