import { RouterProvider } from 'react-router';
import { router } from './router';
import { Toaster } from '@/components/ui/sonner';

function App() {
  return (
    <>
      <RouterProvider router={router} />
      <Toaster position="bottom-right" />
    </>
  );
}

export default App;
