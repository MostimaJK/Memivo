import React from 'react';
import {type ModelEntry} from './api';
import {useI18n} from './i18n';

export function InsightFaceGuide({entry}:{entry:ModelEntry}) {
  const {t}=useI18n();
  return <section className="insightface-guide" aria-label={t('InsightFace 下载与文件说明')}>
    <h3>{t('第一次使用：推荐 buffalo_l')}</h3>
    <p>{t('buffalo_l 适合作为常规照片整理的起点；m 使用较小检测器但识别模型相同，s/sc 更轻量，antelopev2 使用更大的识别模型。实际效果请用自己的照片验证。')}</p>
    <p>{t('当前选择：下载 {0}.zip，不是 GitHub 的 Source code 压缩包。',[entry.id])}</p>
    <div className="engine-actions"><a className="official-model-link" href={entry.archive} target="_blank" rel="noopener noreferrer">{t('下载 {0}.zip',[entry.id])} ↗</a><a className="official-model-link" href={entry.release_page} target="_blank" rel="noopener noreferrer">{t('官方发布页（备用入口）')} ↗</a></div>
    <h4>{t('只需这两个 ONNX 文件')}</h4>
    <div className="model-file-table"><table><thead><tr><th>{t('压缩包中的文件')}</th><th>{t('作用与放置位置')}</th></tr></thead><tbody>
      <tr><td><code>{entry.detector_file}</code></td><td>{t('人脸检测与五点定位')}<br/><code>model/face/detector/</code></td></tr>
      <tr><td><code>{entry.recognition_file}</code></td><td>{t('身份特征提取与人物匹配')}<br/><code>model/face/recognition/</code></td></tr>
    </tbody></table></div>
    <p>{t('解压后按文件名取出这两个文件；部分压缩包还有一层同名目录。不要把整个压缩包放入模型目录，也不要把所有 ONNX 都放进识别目录。')}</p>
    <details><summary>{t('其他文件是什么？为什么数量不一样？')}</summary>
      {entry.has_extra_models?<><p>{t('此系列常见完整包包含 5 个 ONNX：以上两个，加上下面三个；请按文件名判断用途，而不是按文件顺序或数量猜测。')}</p><ul>
        <li><code>2d106det.onnx</code> — {t('106 点二维人脸关键点；不是人脸检测或身份识别模型。')}</li>
        <li><code>1k3d68.onnx</code> — {t('68 点三维人脸关键点；当前相册整理不使用。')}</li>
        <li><code>genderage.onnx</code> — {t('年龄与性别估计；当前相册整理不使用。')}</li>
      </ul></>:<p>{t('buffalo_sc 是精简包，通常只有检测和识别这两个 ONNX，不含关键点和年龄／性别模型。')}</p>}
      <p>{t('如果你看到 4 个文件，先核对压缩包名称、内层目录和具体文件名；Memivo 需要的是上表两个文件，辅助模型缺少不会阻止当前整理流程。检测模型已提供对齐所需的五点，不必额外加载 106 点模型。')}</p>
    </details>
    <p>{t('如果已经使用 LVFace，只取检测文件即可；识别目录继续使用 LVFace，不需要再切换到本包的 ArcFace。')}</p>
    <p>{t('放好后点击“扫描模型”，在设置中确认检测和识别下拉框，再安装人物识别引擎。多个候选不会替你覆盖已有选择。')}</p>
    <p className="microcopy">{t('官方直链可能调整或受网络限制；失效时请从备用发布页 Assets 查找同名 ZIP，或使用官方模型说明页的下载入口。这里提供手动下载链接，尚未提供该压缩包的程序内校验下载。')}</p>
  </section>;
}
