// frontend/src/components/CountSlider.js
import React from 'react';
import { Box, Slider, Typography, Tooltip, Input, Grid } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

const CountSlider = ({ label, value, onChange, max, min = 1, step = 1, tooltip }) => {
    
    const handleSliderChange = (event, newValue) => {
        onChange(newValue);
    };

    const handleInputChange = (event) => {
        onChange(event.target.value === '' ? '' : Number(event.target.value));
    };

    const handleBlur = () => {
        if (value < min) {
            onChange(min);
        } else if (value > max) {
            onChange(max);
        }
    };
    
    // Определяем цвет дорожки слайдера в зависимости от значения
    const progress = (value / max) * 100;
    const trackColor = progress > 85 ? 'error.main' : progress > 60 ? 'warning.main' : 'primary.main';

    return (
        <Box>
            <Box display="flex" alignItems="center" mb={1}>
                <Typography gutterBottom sx={{ fontWeight: 500, mb: 0 }}>
                    {label}
                </Typography>
                {tooltip && (
                    <Tooltip title={tooltip} placement="top" arrow>
                        <InfoOutlinedIcon fontSize="small" color="secondary" sx={{ ml: 0.5, cursor: 'help' }} />
                    </Tooltip>
                )}
            </Box>
            <Grid container spacing={2} alignItems="center">
                <Grid item xs>
                    <Slider
                        value={typeof value === 'number' ? value : min}
                        onChange={handleSliderChange}
                        aria-labelledby="input-slider"
                        min={min}
                        max={max}
                        step={step}
                        sx={{
                            '& .MuiSlider-track': {
                                background: trackColor,
                                transition: 'background 0.3s ease',
                            },
                             '& .MuiSlider-thumb': {
                                backgroundColor: trackColor,
                                transition: 'background 0.3s ease',
                             }
                        }}
                    />
                </Grid>
                <Grid item>
                    <Input
                        value={value}
                        size="small"
                        onChange={handleInputChange}
                        onBlur={handleBlur}
                        inputProps={{
                            step: step,
                            min: min,
                            max: max,
                            type: 'number',
                            'aria-labelledby': 'input-slider',
                        }}
                        sx={{ width: '60px' }}
                    />
                </Grid>
            </Grid>
        </Box>
    );
};

export default CountSlider;