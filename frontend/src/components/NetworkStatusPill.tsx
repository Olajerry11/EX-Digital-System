/* eslint-disable @typescript-eslint/no-unused-vars */
// EX-DIGITAL — Network Status Pill Component
import { motion, AnimatePresence } from 'framer-motion';
import { Wifi, WifiOff } from 'lucide-react';
import { useNetworkStatus } from '../lib/useNetworkStatus';

export default function NetworkStatusPill() {
  const isOnline = useNetworkStatus();

  return (
    <AnimatePresence>
      {!isOnline && (
        <motion.div
          initial={{ opacity: 0, y: 20, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.9 }}
          className="network-pill"
          style={{ background: 'rgba(255,64,96,0.15)', borderColor: 'rgba(255,64,96,0.35)' }}
        >
          <WifiOff size={12} className="text-red-400" />
          <span className="text-red-300">Offline — scans queued locally</span>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
