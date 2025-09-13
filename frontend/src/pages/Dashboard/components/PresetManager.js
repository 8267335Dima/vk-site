// --- frontend/src/pages/Dashboard/components/PresetManager.js ---
import React, { useState } from 'react';
import { Box, FormControl, InputLabel, Select, MenuItem, Button, IconButton, ListItemText, Dialog, DialogTitle, DialogContent, TextField, DialogActions, CircularProgress, Typography, Stack, Divider } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchFilterPresets, createFilterPreset, deleteFilterPreset } from 'api';
import { toast } from 'react-hot-toast';

const PresetManager = ({ actionKey, currentFilters, onApply }) => {
    const queryClient = useQueryClient();
    const [selectedPresetId, setSelectedPresetId] = useState('');
    const [isSaveDialogOpen, setSaveDialogOpen] = useState(false);
    const [presetName, setPresetName] = useState('');

    const { data: presets, isLoading } = useQuery({
        queryKey: ['filterPresets', actionKey],
        queryFn: () => fetchFilterPresets(actionKey),
        enabled: !!actionKey,
    });

    const createMutation = useMutation({
        mutationFn: createFilterPreset,
        onSuccess: () => {
            toast.success("Пресет успешно сохранен!");
            queryClient.invalidateQueries({ queryKey: ['filterPresets', actionKey] });
            setSaveDialogOpen(false);
            setPresetName('');
        },
        onError: (err) => toast.error(err.response?.data?.detail || "Ошибка сохранения"),
    });

    const deleteMutation = useMutation({
        mutationFn: deleteFilterPreset,
        onSuccess: () => {
            toast.success("Пресет удален.");
            queryClient.invalidateQueries({ queryKey: ['filterPresets', actionKey] });
            setSelectedPresetId('');
        },
        onError: (err) => toast.error(err.response?.data?.detail || "Ошибка удаления"),
    });

    const handleSelectPreset = (event) => {
        const id = event.target.value;
        setSelectedPresetId(id);
        const selected = presets.find(p => p.id === id);
        if (selected) {
            onApply(selected.filters);
        }
    };

    const handleDeletePreset = (event, id) => {
        event.stopPropagation();
        deleteMutation.mutate(id);
    };

    const handleSavePreset = () => {
        if (!presetName.trim()) {
            toast.error("Название пресета не может быть пустым.");
            return;
        }
        createMutation.mutate({
            name: presetName,
            action_type: actionKey,
            filters: currentFilters,
        });
    };

    return (
        <Box>
            <Stack direction="row" spacing={2} alignItems="center">
                <FormControl fullWidth size="small" disabled={isLoading}>
                    <InputLabel>Пресеты фильтров</InputLabel>
                    <Select
                        value={selectedPresetId}
                        label="Пресеты фильтров"
                        onChange={handleSelectPreset}
                        renderValue={(selected) => presets?.find(p => p.id === selected)?.name || ''}
                    >
                        <MenuItem value="" disabled><em>Выберите пресет</em></MenuItem>
                        <Divider />
                        {presets?.map(preset => (
                            <MenuItem key={preset.id} value={preset.id}>
                                <ListItemText primary={preset.name} />
                                <IconButton edge="end" size="small" onClick={(e) => handleDeletePreset(e, preset.id)} disabled={deleteMutation.isLoading}>
                                    <DeleteIcon fontSize="small" />
                                </IconButton>
                            </MenuItem>
                        ))}
                         {presets?.length === 0 && <MenuItem disabled><Typography variant="body2" color="text.secondary" sx={{px: 2}}>Нет сохраненных пресетов</Typography></MenuItem>}
                    </Select>
                </FormControl>
                <Button variant="outlined" size="small" startIcon={<AddIcon />} onClick={() => setSaveDialogOpen(true)}>
                    Сохранить
                </Button>
            </Stack>

            <Dialog open={isSaveDialogOpen} onClose={() => setSaveDialogOpen(false)}>
                <DialogTitle>Сохранить пресет фильтров</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        margin="dense"
                        label="Название пресета"
                        fullWidth
                        variant="standard"
                        value={presetName}
                        onChange={(e) => setPresetName(e.target.value)}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setSaveDialogOpen(false)}>Отмена</Button>
                    <Button onClick={handleSavePreset} disabled={createMutation.isLoading}>
                        {createMutation.isLoading ? <CircularProgress size={22} /> : "Сохранить"}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default PresetManager;