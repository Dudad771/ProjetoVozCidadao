-- Projeto: VozCidadão
-- DML: dados fictícios exclusivamente para demonstração.
-- Substituir/validar os registros com dados de fonte oficial da Prefeitura
-- ou da Secretaria Municipal de Saúde antes de apresentar como dados reais.

USE vozcidadao;

INSERT INTO unidades_saude
(id_unidade, nome, tipo, unidade_publica, endereco, bairro, cidade, uf,
 cep, telefone, latitude, longitude, atendimento_24h, ativa)
VALUES
(1, 'Hospital Público Exemplo Central', 'HOSPITAL', TRUE,
 'Rua de Demonstração, 100', 'Centro', 'Recife', 'PE',
 '50000-000', '(81) 0000-0000', -8.0631000, -34.8711000, TRUE, TRUE),
(2, 'UPA Exemplo Norte', 'UPA', TRUE,
 'Avenida de Demonstração, 250', 'Casa Amarela', 'Recife', 'PE',
 '52000-000', '(81) 0000-0001', -8.0270000, -34.9000000, TRUE, TRUE),
(3, 'UBS Exemplo Boa Vista', 'UBS', TRUE,
 'Rua Modelo, 45', 'Boa Vista', 'Recife', 'PE',
 '50050-000', '(81) 0000-0002', -8.0575000, -34.8850000, FALSE, TRUE)
ON DUPLICATE KEY UPDATE
 nome = VALUES(nome),
 tipo = VALUES(tipo),
 unidade_publica = VALUES(unidade_publica),
 endereco = VALUES(endereco),
 bairro = VALUES(bairro),
 cidade = VALUES(cidade),
 uf = VALUES(uf),
 cep = VALUES(cep),
 telefone = VALUES(telefone),
 latitude = VALUES(latitude),
 longitude = VALUES(longitude),
 atendimento_24h = VALUES(atendimento_24h),
 ativa = VALUES(ativa);

INSERT INTO servicos (id_servico, nome, descricao, ativo)
VALUES
(1, 'Clínica médica', 'Atendimento médico clínico geral.', TRUE),
(2, 'Pediatria', 'Atendimento médico para crianças.', TRUE),
(3, 'Vacinação', 'Aplicação de vacinas conforme calendário vigente.', TRUE),
(4, 'Atendimento de urgência', 'Avaliação e atendimento de urgências.', TRUE)
ON DUPLICATE KEY UPDATE
 nome = VALUES(nome), descricao = VALUES(descricao), ativo = VALUES(ativo);

INSERT INTO unidade_servico (id_unidade, id_servico, observacoes)
VALUES
(1, 1, 'Exemplo ilustrativo'),
(1, 2, 'Exemplo ilustrativo'),
(1, 4, 'Exemplo ilustrativo'),
(2, 1, 'Exemplo ilustrativo'),
(2, 4, 'Exemplo ilustrativo'),
(3, 1, 'Exemplo ilustrativo'),
(3, 3, 'Exemplo ilustrativo')
ON DUPLICATE KEY UPDATE observacoes = VALUES(observacoes);

INSERT INTO horarios_atendimento
(id_horario, id_unidade, dia_semana, hora_abertura, hora_fechamento, fechado, observacoes)
VALUES
(1, 1, 'SEGUNDA', '00:00:00', '23:59:00', FALSE, 'Atendimento 24h; horário ilustrativo'),
(2, 1, 'TERCA', '00:00:00', '23:59:00', FALSE, 'Atendimento 24h; horário ilustrativo'),
(3, 1, 'QUARTA', '00:00:00', '23:59:00', FALSE, 'Atendimento 24h; horário ilustrativo'),
(4, 1, 'QUINTA', '00:00:00', '23:59:00', FALSE, 'Atendimento 24h; horário ilustrativo'),
(5, 1, 'SEXTA', '00:00:00', '23:59:00', FALSE, 'Atendimento 24h; horário ilustrativo'),
(6, 1, 'SABADO', '00:00:00', '23:59:00', FALSE, 'Atendimento 24h; horário ilustrativo'),
(7, 1, 'DOMINGO', '00:00:00', '23:59:00', FALSE, 'Atendimento 24h; horário ilustrativo'),
(8, 2, 'SEGUNDA', '07:00:00', '19:00:00', FALSE, 'Horário ilustrativo'),
(9, 2, 'TERCA', '07:00:00', '19:00:00', FALSE, 'Horário ilustrativo'),
(10, 2, 'QUARTA', '07:00:00', '19:00:00', FALSE, 'Horário ilustrativo'),
(11, 2, 'QUINTA', '07:00:00', '19:00:00', FALSE, 'Horário ilustrativo'),
(12, 2, 'SEXTA', '07:00:00', '19:00:00', FALSE, 'Horário ilustrativo'),
(13, 2, 'SABADO', NULL, NULL, TRUE, 'Fechado no exemplo'),
(14, 2, 'DOMINGO', NULL, NULL, TRUE, 'Fechado no exemplo'),
(15, 3, 'SEGUNDA', '08:00:00', '17:00:00', FALSE, 'Horário ilustrativo'),
(16, 3, 'TERCA', '08:00:00', '17:00:00', FALSE, 'Horário ilustrativo'),
(17, 3, 'QUARTA', '08:00:00', '17:00:00', FALSE, 'Horário ilustrativo'),
(18, 3, 'QUINTA', '08:00:00', '17:00:00', FALSE, 'Horário ilustrativo'),
(19, 3, 'SEXTA', '08:00:00', '17:00:00', FALSE, 'Horário ilustrativo'),
(20, 3, 'SABADO', NULL, NULL, TRUE, 'Fechado no exemplo'),
(21, 3, 'DOMINGO', NULL, NULL, TRUE, 'Fechado no exemplo')
ON DUPLICATE KEY UPDATE
 hora_abertura = VALUES(hora_abertura),
 hora_fechamento = VALUES(hora_fechamento),
 fechado = VALUES(fechado),
 observacoes = VALUES(observacoes);
