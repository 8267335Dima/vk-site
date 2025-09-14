import { useQuery } from '@tanstack/react-query';
import { fetchUserInfo } from '@/shared/api';
import { useStore } from '@/app/store';

export const useCurrentUser = () => {
  const token = useStore((state) => state.token);
  const activeProfileId = useStore((state) => state.activeProfileId);
  const { setUnauthenticated, setUserInfo } = useStore(
    (state) => state.actions
  );

  return useQuery({
    queryKey: ['currentUser', activeProfileId],
    queryFn: fetchUserInfo,
    enabled: !!token,
    staleTime: 1000 * 60 * 15,
    gcTime: 1000 * 60 * 30,
    select: (response) => response.data,
    retry: false,
    onSuccess: (data) => {
      setUserInfo(data);
    },
    onError: (error) => {
      if (error.response?.status === 401) {
        setUnauthenticated();
      }
    },
  });
};
