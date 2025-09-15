import React from 'react';
import { FormControlLabel, Switch as MuiSwitch } from '@mui/material';
import { useFormContext, Controller } from 'react-hook-form';

export const SwitchField = ({
  name,
  label,
  defaultValue = false,
  rules,
  ...props
}) => {
  const { control } = useFormContext();

  return (
    <FormControlLabel
      control={
        <Controller
          name={name}
          control={control}
          defaultValue={defaultValue}
          rules={rules}
          render={({ field }) => (
            <MuiSwitch
              {...field}
              checked={!!field.value}
              onChange={(e) => field.onChange(e.target.checked)}
            />
          )}
        />
      }
      label={label}
      {...props}
    />
  );
};
