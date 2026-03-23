import React from 'react';
import Lottie from 'lottie-react';
import animationData from '../../assets/Demo.json';
import '../forex/Forex.css';
import './Demo.css';

export default function DemoHome({ t: globalT, onStartStudy }) {
  const t = globalT.forexAnalytics;

  return (
    <div className="profile-wrapper">      
      <div className="analytics-hero">
        <h1 className="settings-main-title">{t.title}</h1>
        <p className="subtitle">{t.subtitle}</p>
        <p className="description">{t.description}</p>
      </div>

      <div className="lottie-animation-wrapper">
        <Lottie animationData={animationData} loop={true} className="hero-lottie" />
      </div>

      <div className="actions-wrapper" style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
        <button className="forex-cta-btn" onClick={onStartStudy}>
          {globalT.demoSettings?.startStudy || 'Start Study'}
        </button>
      </div>
    </div>
  );
}