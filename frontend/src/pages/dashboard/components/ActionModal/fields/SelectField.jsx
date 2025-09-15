import React from 'react';
import {
  FormControl,
  InputLabel,
  Select as MuiSelect,
  FormHelperText,
} from '@mui/material';
import { useFormContext, Controller } from 'react-hook-form';

export const SelectField = ({
  name,
  label,
  defaultValue = '',
  children,
  rules,
  ...props
}) => {
  const { control } = useFormContext();

  return (
    <Controller
      name={name}
      control={control}
      defaultValue={defaultValue}
      rules={rules}
      render={({ field, fieldState: { error } }) => (
        <FormControl fullWidth size="small" error={!!error}>
          <InputLabel>{label}</InputLabel>
          <MuiSelect {...field} label={label} {...props}>
            {children}
          </MuiSelect>
          {error && <FormHelperText>{error.message}</FormHelperText>}
        </FormControl>
      )}
    />
  );
};
