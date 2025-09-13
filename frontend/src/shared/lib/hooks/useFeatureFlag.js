import { useCurrentUser } from './useCurrentUser';

export const useFeatureFlag = () => {
  const { data: currentUser } = useCurrentUser();
  const availableFeatures = currentUser?.available_features || [];

  const isFeatureAvailable = (featureKey) => {
    return availableFeatures.includes(featureKey);
  };

  return { isFeatureAvailable };
};
