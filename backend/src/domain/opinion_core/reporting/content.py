import hashlib
from datetime import datetime, timezone
from opinion_core.schemas.artifacts import ContentBlock,ContentBundle,EvidenceCard


def build_content(event_id, run_id, observations, evidence, versions, forum=None, prediction=None, scenarios=None):
    metrics = {'input_count':observations['input_n'],'missing_time_count':observations['missing_time_n'],
               'window_count':len(observations['windows']),
               'joint_valid_count':sum(w['joint_n'] for w in observations['windows'])}
    calc_id = 'c-'+hashlib.sha256(str(sorted(versions.items())).encode()).hexdigest()
    calc = EvidenceCard(evidence_id=calc_id,kind='calculation',title='固定窗口与有效性掩码统计',
             excerpt='观测窗口、分母及字段状态来自确定性计算。',source_ref=versions['observations'],
             retrieved_at=datetime.now(timezone.utc),content_sha256=versions['observations'].removeprefix('a-'))
    blocks = [ContentBlock(block_id='inventory',kind='observed',title='数据与覆盖',
        text='输入记录 {{input_count}} 条；发布时间缺失 {{missing_time_count}} 条；窗口 {{window_count}} 个；联合字段有效 {{joint_valid_count}} 条。',
        numeric_refs=list(metrics),evidence_refs=[calc_id])]
    for i,claim in enumerate((forum or {}).get('claims',[])):
        blocks.append(ContentBlock(block_id=f'interpretation-{i}',kind='interpretation',title='证据解释',
                                   text=claim['text'],evidence_refs=claim['evidence_refs']))
    if prediction and prediction.get('status')=='partial':
        blocks.append(ContentBlock(block_id='forecast-unavailable',kind='interpretation',title='预测尚不可用',
                                   text='缺少足够的联合有效观测，未生成模型预测；已保留可用的分布复盘结果。'))
    elif prediction:
        metrics['forecast_horizon'] = len(prediction['steps'])
        blocks.append(ContentBlock(block_id='forecast',kind='forecast',title='实验性预测',
                      text='预测 {{forecast_horizon}} 个窗口。区间为模型集合离散范围，尚未校准覆盖率。',
                      numeric_refs=['forecast_horizon'],artifact_refs=[versions['forecast']]))
    if scenarios and scenarios.get('status')=='partial':
        blocks.append(ContentBlock(block_id='scenarios-unavailable',kind='interpretation',title='情景尚不可用',
                                   text='数值起点不可用，未生成条件情景。'))
    elif scenarios:
        metrics['scenario_count'] = len(scenarios['branches'])
        blocks.append(ContentBlock(block_id='scenarios',kind='simulated',title='条件情景',
                      text='构建 {{scenario_count}} 个情景分支；差异取决于模型与所列假设，不作为现实干预因果效应。',
                      numeric_refs=['scenario_count'],artifact_refs=[versions['scenarios']]))
    blocks.append(ContentBlock(block_id='limitations',kind='interpretation',title='方法与限制',
                  text='模型弱标注自动进入分析。拒判、失败与缺失分别记录；真实模型质量、预测收益及图片增益需由后续独立评测确定。'))
    unique = {e['evidence_id']:e for e in evidence}
    unique[calc_id] = calc.model_dump(mode='json')
    return ContentBundle(event_id=event_id,run_id=run_id,blocks=blocks,evidence=list(unique.values()),
                         metrics=metrics,source_versions=versions).model_dump(mode='json')
