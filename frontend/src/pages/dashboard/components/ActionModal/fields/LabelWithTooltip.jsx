import React from 'react';
import { Box, Tooltip, Typography, IconButton } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

export const LabelWithTooltip = ({ title, tooltipText, ...props }) => {
  return (
    <Box display="flex" alignItems="center" component="span" {...props}>
      <Typography variant="body1" component="span" sx={{ lineHeight: 1 }}>
        {title}
      </Typography>
      <Tooltip title={tooltipText} placement="top" arrow>
        <IconButton
          size="small"
          sx={{
            ml: 0.5,
            p: 0.25,
            color: 'secondary.main',
            cursor: 'help',
          }}
          aria-label={tooltipText}
        >
          <InfoOutlinedIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  );
};
