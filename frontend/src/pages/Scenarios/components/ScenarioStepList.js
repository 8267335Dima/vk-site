// frontend/src/pages/Scenarios/components/ScenarioStepList.js
import React from 'react';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import { Paper, Stack, Box, Chip, FormControl, Select, MenuItem, IconButton, Typography } from '@mui/material';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import DeleteIcon from '@mui/icons-material/Delete';
import { actionOptions } from './constants';
import { StepSettings } from './ScenarioStepSettings'; // <-- Корректный импорт настроек

// --- ИСПРАВЛЕНИЕ: Этот компонент был случайно удален и заменен другим. Теперь он восстановлен. ---
const ScenarioStep = ({ step, index, onRemove, onChange, onBatchChange }) => (
    <Paper sx={{ p: 2, mb: 2, '&:hover': { boxShadow: 3 } }}>
        <Stack direction="row" spacing={2} alignItems="center">
            <Box sx={{ cursor: 'grab' }}><DragIndicatorIcon color="disabled" /></Box>
            <Chip label={`Шаг ${index + 1}`} />
            <FormControl fullWidth size="small">
                <Select value={step.action_type} onChange={(e) => onChange(step.localId, 'action_type', e.target.value)}>
                    {actionOptions.map(opt => <MenuItem key={opt.key} value={opt.key}>{opt.title}</MenuItem>)}
                </Select>
            </FormControl>
            <IconButton onClick={() => onRemove(step.localId)}><DeleteIcon color="error" /></IconButton>
        </Stack>
        <StepSettings 
            step={step} 
            onSettingsChange={(newSettings) => onChange(step.localId, 'settings', newSettings)} 
            onBatchChange={onBatchChange}
        />
    </Paper>
);

// --- ИСПРАВЛЕНИЕ: Экспорт компонента ScenarioStepList восстановлен. ---
export const ScenarioStepList = ({ steps, setSteps, onStepChange, onStepRemove, onBatchChange }) => {
    const onDragEnd = (result) => {
        if (!result.destination) return;
        const items = Array.from(steps);
        const [reorderedItem] = items.splice(result.source.index, 1);
        items.splice(result.destination.index, 0, reorderedItem);
        setSteps(items);
    };

    return (
        <DragDropContext onDragEnd={onDragEnd}>
            <Typography variant="h6">Последовательность действий</Typography>
            <Droppable droppableId="steps">
                {(provided) => (
                    <Box {...provided.droppableProps} ref={provided.innerRef} sx={{mt: 2}}>
                        {steps.map((step, index) => (
                            <Draggable key={step.localId} draggableId={String(step.localId)} index={index}>
                                {(provided) => (
                                    <div ref={provided.innerRef} {...provided.draggableProps} {...provided.dragHandleProps}>
                                        <ScenarioStep 
                                            step={step} 
                                            index={index}
                                            onRemove={onStepRemove}
                                            onChange={onStepChange}
                                            onBatchChange={onBatchChange}
                                        />
                                    </div>
                                )}
                            </Draggable>
                        ))}
                        {provided.placeholder}
                    </Box>
                )}
            </Droppable>
        </DragDropContext>
    );
};