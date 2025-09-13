import React from 'react';
import { TextField as MuiTextField } from '@mui/material';
import { useFormContext, Controller } from 'react-hook-form';

export const TextField = ({
  name,
  label,
  defaultValue = '',
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
        <MuiTextField
          {...field}
          label={label}
          error={!!error}
          helperText={error ? error.message : props.helperText}
          fullWidth
          size="small"
          variant="outlined"
          {...props}
        />
      )}
    />
  );
};
