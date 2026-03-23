import React, { useState, useEffect } from 'react';
import Lottie from 'lottie-react';
import animationData from '../../assets/loader.json';
import './Loader.css';

export default function Loader({ t }) {
  const [phraseIndex, setPhraseIndex] = useState(0);
  const phrases = t.loadingPhrases || ["Loading..."];

  useEffect(() => {
    const interval = setInterval(() => {
      setPhraseIndex((prev) => (prev + 1) % phrases.length);
    }, 1800);
    
    return () => clearInterval(interval);
  }, [phrases.length]);

  return (
    <div className="fullscreen-loader">
      <div className="loader-content">
        <div className="loader-lottie">
          <Lottie 
            animationData={animationData} 
            loop={true} 
            style={{ width: 160, height: 160 }} 
          />
        </div>
        <h2 className="loader-title">{t.projectName}</h2>
        <div className="loader-phrase-container">
          <p className="loader-phrase fade-phrase-anim" key={phraseIndex}>
            {phrases[phraseIndex]}
          </p>
        </div>
      </div>
    </div>
  );
}