import React from 'react';
import Lottie from 'lottie-react';
import animationData from '../../assets/animation.json';
import './Binary.css';

export default function BinaryHome({ t: globalT, onStartSignal }) {
  const t = globalT.binaryAnalytics;

  return (
    <div className="profile-wrapper">
      <div className="analytics-hero">
        <h1 className="settings-main-title">{t.title}</h1>
        <p className="subtitle">{t.subtitle}</p>
        <p className="description">{t.description}</p>
      </div>

      <div className="lottie-animation-wrapper">
        <Lottie 
          animationData={animationData} 
          loop={true} 
          style={{ width: 220, height: 220 }} 
        />
      </div>

      <div className="actions-wrapper">
        <button className="binary-cta-btn" onClick={onStartSignal}>
          {t.cta}
        </button>
      </div>

      <div className="disclaimer-box">
        <p>{t.disclaimer}</p>
      </div>
    </div>
  );
}