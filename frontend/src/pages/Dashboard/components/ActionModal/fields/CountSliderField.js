// frontend/src/pages/Dashboard/components/ActionModal/fields/CountSliderField.js
import React from 'react';
import { useFormContext, Controller } from 'react-hook-form';
// ИСПРАВЛЕНО
import CountSlider from '../../../../../components/CountSlider';

export const CountSliderField = ({ name, label, max, defaultValue, ...props }) => {
    const { control } = useFormContext();

    return (
        <Controller
            name={name}
            control={control}
            defaultValue={defaultValue}
            render={({ field }) => (
                <CountSlider
                    label={label}
                    value={field.value}
                    onChange={field.onChange}
                    max={max}
                    {...props}
                />
            )}
        />
    );
};